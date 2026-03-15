"""Generation service — DocumentRun lifecycle management.

Orchestrates document generation runs and revisions.
"""
from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.models.document import (
    DocumentRun,
    DocumentRevision,
    ProjectCurrentDocument,
    DocumentAsset,
)
from services.web_app.db.models.base import new_cuid


async def create_document_run(
    *,
    db: AsyncSession,
    org_id: str,
    project_id: str,
    doc_type: str,
    created_by: str,
    analysis_snapshot_id: str | None = None,
    params: dict | None = None,
    engine_version: str | None = None,
    mode_used: str | None = None,
) -> DocumentRun:
    """Create a new DocumentRun with status=queued.

    Args:
        db: Database session (caller manages transaction)
        org_id: Organization ID
        project_id: BidProject ID
        doc_type: One of DocType enum values
        created_by: User ID who initiated the run
        analysis_snapshot_id: Optional snapshot reference
        params: Optional generation parameters
        engine_version: Optional engine version tag
        mode_used: Optional generation mode (strict_template/starter/upgrade)

    Returns:
        Created DocumentRun instance (not committed)
    """
    run = DocumentRun(
        id=new_cuid(),
        org_id=org_id,
        project_id=project_id,
        analysis_snapshot_id=analysis_snapshot_id,
        doc_type=doc_type,
        status="queued",
        params_json=params,
        engine_version=engine_version,
        mode_used=mode_used,
        created_by=created_by,
    )
    db.add(run)
    await db.flush()
    return run


async def start_document_run(*, db: AsyncSession, run: DocumentRun) -> None:
    """Transition DocumentRun to running status.

    Args:
        db: Database session
        run: DocumentRun instance to update
    """
    run.status = "running"
    run.started_at = datetime.now(UTC)
    await db.flush()


async def complete_document_run(
    *,
    db: AsyncSession,
    run: DocumentRun,
    content_json: dict,
    content_schema: str,
    quality_report: dict | None = None,
    output_files: list[dict] | None = None,
    title: str | None = None,
) -> DocumentRevision:
    """Complete a DocumentRun and create its DocumentRevision.

    Performs:
    1. Transition run to completed
    2. Create DocumentRevision (status=draft, source=ai_generated)
    3. Update ProjectCurrentDocument pointer
    4. Mark previous completed runs as superseded

    Args:
        db: Database session
        run: DocumentRun to complete
        content_json: Generated content (sections etc.)
        content_schema: Content schema version
        quality_report: Optional quality check results
        output_files: Optional list of output file metadata
        title: Optional revision title

    Returns:
        Created DocumentRevision instance
    """
    # 1. Transition run to completed
    run.status = "completed"
    run.completed_at = datetime.now(UTC)

    # 2. Get next revision number
    rev_num = await _get_next_revision_number(
        db=db, project_id=run.project_id, doc_type=run.doc_type
    )

    # 3. Create revision
    revision = DocumentRevision(
        id=new_cuid(),
        org_id=run.org_id,
        project_id=run.project_id,
        doc_type=run.doc_type,
        run_id=run.id,
        revision_number=rev_num,
        source="ai_generated",
        status="draft",
        title=title,
        content_json=content_json,
        content_schema=content_schema,
        quality_report_json=quality_report,
        created_by=run.created_by,
    )
    db.add(revision)
    await db.flush()

    # 4. Update ProjectCurrentDocument
    await _update_current_document(
        db=db,
        org_id=run.org_id,
        project_id=run.project_id,
        doc_type=run.doc_type,
        revision_id=revision.id,
    )

    # 5. Mark previous completed runs as superseded
    await _supersede_previous_runs(
        db=db, project_id=run.project_id, doc_type=run.doc_type, current_run_id=run.id
    )

    # 6. Handle output files (Phase 1: mark assets as verified if uploaded)
    if output_files:
        await _verify_output_assets(db=db, revision_id=revision.id, files=output_files)

    await db.flush()
    return revision


async def fail_document_run(
    *, db: AsyncSession, run: DocumentRun, error: str
) -> None:
    """Transition DocumentRun to failed status.

    Args:
        db: Database session
        run: DocumentRun to fail
        error: Error message
    """
    run.status = "failed"
    run.error_message = error
    run.completed_at = datetime.now(UTC)
    await db.flush()


# ============================================================================
# Internal helpers
# ============================================================================


async def _get_next_revision_number(
    *, db: AsyncSession, project_id: str, doc_type: str
) -> int:
    """Get next revision number for a doc_type in a project."""
    result = await db.execute(
        select(DocumentRevision.revision_number)
        .where(
            DocumentRevision.project_id == project_id,
            DocumentRevision.doc_type == doc_type,
        )
        .order_by(DocumentRevision.revision_number.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return (row or 0) + 1


async def _update_current_document(
    *,
    db: AsyncSession,
    org_id: str,
    project_id: str,
    doc_type: str,
    revision_id: str,
) -> None:
    """Upsert ProjectCurrentDocument pointer."""
    result = await db.execute(
        select(ProjectCurrentDocument).where(
            ProjectCurrentDocument.project_id == project_id,
            ProjectCurrentDocument.doc_type == doc_type,
        )
    )
    current = result.scalar_one_or_none()

    if current:
        current.current_revision_id = revision_id
        current.updated_at = datetime.now(UTC)
    else:
        current = ProjectCurrentDocument(
            id=new_cuid(),
            org_id=org_id,
            project_id=project_id,
            doc_type=doc_type,
            current_revision_id=revision_id,
        )
        db.add(current)

    await db.flush()


async def _supersede_previous_runs(
    *,
    db: AsyncSession,
    project_id: str,
    doc_type: str,
    current_run_id: str,
) -> None:
    """Mark all previous completed runs as superseded."""
    result = await db.execute(
        select(DocumentRun).where(
            DocumentRun.project_id == project_id,
            DocumentRun.doc_type == doc_type,
            DocumentRun.status == "completed",
            DocumentRun.id != current_run_id,
        )
    )
    runs = result.scalars().all()
    for run in runs:
        run.status = "superseded"
    await db.flush()


async def _verify_output_assets(
    *, db: AsyncSession, revision_id: str, files: list[dict]
) -> None:
    """Verify uploaded DocumentAssets by matching ETag/content_hash.

    Phase 1: Simply mark assets with matching revision_id as verified.
    Full implementation would check presigned upload completion.

    Args:
        db: Database session
        revision_id: Revision ID to attach assets to
        files: List of file metadata dicts (expected keys: asset_type, storage_uri, ...)
    """
    # Phase 1: Simple implementation — mark assets as verified if they have
    # upload_status='uploaded' and match the revision_id
    result = await db.execute(
        select(DocumentAsset).where(
            DocumentAsset.revision_id == revision_id,
            DocumentAsset.upload_status == "uploaded",
        )
    )
    assets = result.scalars().all()

    for asset in assets:
        # In full implementation, would verify ETag/content_hash here
        asset.upload_status = "verified"

    await db.flush()
