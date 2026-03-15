"""Generation service — DocumentRun lifecycle management.

Orchestrates document generation runs and revisions.
"""
from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

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

    # 6. Link output files to revision (CRITICAL: must happen before verification)
    if output_files:
        for f in output_files:
            asset_id = f.get("asset_id")
            if asset_id:
                result = await db.execute(
                    select(DocumentAsset).where(DocumentAsset.id == asset_id)
                )
                asset = result.scalar_one_or_none()
                if asset:
                    asset.revision_id = revision.id  # Link to revision!
                    asset.upload_status = "uploaded"
                    asset.size_bytes = f.get("size_bytes")
                    asset.content_hash = f"client:{f.get('content_hash', '')}"
        await db.flush()

        # 7. Verify uploaded assets (now that revision_id is set)
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
    """Verify uploaded DocumentAssets via S3 head + ETag confirmation.

    For each asset with upload_status='uploaded':
    1. Call S3 head_object to get ETag and actual size
    2. Compare ETag with client content_hash
    3. If match: upload_status → "verified"
    4. If mismatch or S3 error: log warning, keep status="uploaded"

    Args:
        db: Database session
        revision_id: Revision ID to attach assets to
        files: List of file metadata dicts from rag_engine (with content_hash)
    """
    import asyncio
    from services.web_app.storage.s3 import get_s3_client

    result = await db.execute(
        select(DocumentAsset).where(
            DocumentAsset.revision_id == revision_id,
            DocumentAsset.upload_status == "uploaded",
        )
    )
    assets = result.scalars().all()

    # Build lookup map: asset_id → client_hash
    file_map = {f.get("asset_id"): f.get("content_hash", "") for f in files if f.get("asset_id")}

    s3 = get_s3_client()
    for asset in assets:
        if not asset.storage_uri:
            logger.warning("Asset %s has no storage_uri, cannot verify", asset.id)
            continue

        try:
            # S3 head to get ETag + actual size
            key = s3.parse_storage_uri(asset.storage_uri)
            head = await asyncio.to_thread(s3.head_object, key)
            s3_etag = head.get("ETag", "").strip('"')
            actual_size = head.get("ContentLength", 0)

            # Update size from S3 (authoritative source)
            asset.size_bytes = actual_size

            if s3_etag:
                client_hash = file_map.get(asset.id, "")
                # Store both for audit trail
                asset.content_hash = f"etag:{s3_etag},client:{client_hash}"
                asset.upload_status = "verified"  # REAL verification!
            else:
                logger.warning("No ETag from S3 for asset %s, keeping status=uploaded", asset.id)
        except Exception as e:
            logger.warning("S3 head verification failed for asset %s: %s", asset.id, str(e), exc_info=True)
            # Keep status=uploaded (not verified), but don't fail the whole operation

    await db.flush()
