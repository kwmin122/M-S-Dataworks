"""Generation service tests — DocumentRun lifecycle. Requires PostgreSQL."""
from __future__ import annotations

import pytest
from services.web_app.db.models.org import Organization
from services.web_app.db.models.project import BidProject
from services.web_app.db.models.document import DocumentRun


@pytest.mark.asyncio
async def test_create_document_run(db_session):
    """Creates a DocumentRun with status=queued."""
    from services.web_app.services.generation_service import create_document_run

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트 사업")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session,
        org_id=org.id,
        project_id=project.id,
        doc_type="proposal",
        created_by="u1",
        params={"total_pages": 50},
    )
    assert run.status == "queued"
    assert run.doc_type == "proposal"


@pytest.mark.asyncio
async def test_complete_document_run(db_session):
    """Transitions DocumentRun to completed and creates DocumentRevision."""
    from services.web_app.services.generation_service import (
        create_document_run, complete_document_run,
    )

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session, org_id=org.id, project_id=project.id,
        doc_type="proposal", created_by="u1",
    )

    revision = await complete_document_run(
        db=db_session,
        run=run,
        content_json={"sections": [{"name": "개요", "text": "내용"}]},
        content_schema="proposal_sections_v1",
        quality_report={"issues": [], "total_issues": 0},
        output_files=[],
    )
    assert run.status == "completed"
    assert revision.content_schema == "proposal_sections_v1"
    assert revision.source == "ai_generated"


@pytest.mark.asyncio
async def test_fail_document_run(db_session):
    """Transitions DocumentRun to failed."""
    from services.web_app.services.generation_service import (
        create_document_run, fail_document_run,
    )

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session, org_id=org.id, project_id=project.id,
        doc_type="execution_plan", created_by="u1",
    )

    await fail_document_run(db=db_session, run=run, error="LLM timeout")
    assert run.status == "failed"
    assert run.error_message == "LLM timeout"


@pytest.mark.asyncio
async def test_complete_document_run_links_assets_to_revision(db_session):
    """Verifies that output_files are linked to revision with correct upload_status."""
    from services.web_app.services.generation_service import (
        create_document_run, complete_document_run,
    )
    from services.web_app.db.models.document import DocumentAsset
    from services.web_app.db.models.base import new_cuid
    from sqlalchemy import select

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(project)
    await db_session.flush()

    run = await create_document_run(
        db=db_session, org_id=org.id, project_id=project.id,
        doc_type="proposal", created_by="u1",
    )

    # Pre-create asset (simulating pre-allocation in Task 8)
    asset_id = new_cuid()
    asset = DocumentAsset(
        id=asset_id,
        org_id=org.id,
        project_id=project.id,
        asset_type="docx",
        storage_uri="s3://bucket/key",
        upload_status="presigned_issued",
    )
    db_session.add(asset)
    await db_session.flush()

    # Complete run with output_files
    revision = await complete_document_run(
        db=db_session,
        run=run,
        content_json={"sections": []},
        content_schema="proposal_sections_v1",
        quality_report=None,
        output_files=[
            {"asset_id": asset_id, "size_bytes": 12345, "content_hash": "abc123"}
        ],
    )

    # Verify asset is linked to revision
    result = await db_session.execute(
        select(DocumentAsset).where(DocumentAsset.id == asset_id)
    )
    updated_asset = result.scalar_one()

    assert updated_asset.revision_id == revision.id  # CRITICAL: linked!
    assert updated_asset.upload_status == "uploaded"  # Status transition
    assert updated_asset.size_bytes == 12345
    assert "abc123" in updated_asset.content_hash  # Contains client hash
