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


@pytest.mark.asyncio
async def test_verify_assets_with_etag_success(db_session):
    """S3 head succeeds with ETag → verified."""
    from unittest.mock import Mock, patch
    from services.web_app.services.generation_service import _verify_output_assets
    from services.web_app.db.models.document import DocumentAsset
    from services.web_app.db.models.base import new_cuid
    from sqlalchemy import select

    asset_id = new_cuid()
    asset = DocumentAsset(
        id=asset_id,
        org_id="org1",
        project_id="proj1",
        revision_id="rev1",
        asset_type="docx",
        storage_uri="s3://bucket/test.docx",
        upload_status="uploaded",
    )
    db_session.add(asset)
    await db_session.flush()

    # Mock S3 client
    mock_s3 = Mock()
    mock_s3.parse_storage_uri.return_value = "test.docx"
    mock_s3.head_object.return_value = {"ETag": '"abc123"', "ContentLength": 5000}

    with patch("services.web_app.services.generation_service.get_s3_client", return_value=mock_s3):
        await _verify_output_assets(
            db=db_session,
            revision_id="rev1",
            files=[{"asset_id": asset_id, "content_hash": "client456"}],
        )

    result = await db_session.execute(select(DocumentAsset).where(DocumentAsset.id == asset_id))
    verified_asset = result.scalar_one()

    assert verified_asset.upload_status == "verified"  # CRITICAL: verified!
    assert "etag:abc123" in verified_asset.content_hash
    assert "client:client456" in verified_asset.content_hash
    assert verified_asset.size_bytes == 5000


@pytest.mark.asyncio
async def test_verify_assets_without_etag_stays_uploaded(db_session):
    """S3 head succeeds but no ETag → uploaded 유지."""
    from unittest.mock import Mock, patch
    from services.web_app.services.generation_service import _verify_output_assets
    from services.web_app.db.models.document import DocumentAsset
    from services.web_app.db.models.base import new_cuid
    from sqlalchemy import select

    asset_id = new_cuid()
    asset = DocumentAsset(
        id=asset_id,
        org_id="org1",
        project_id="proj1",
        revision_id="rev1",
        asset_type="docx",
        storage_uri="s3://bucket/test.docx",
        upload_status="uploaded",
    )
    db_session.add(asset)
    await db_session.flush()

    # Mock S3 client - no ETag
    mock_s3 = Mock()
    mock_s3.parse_storage_uri.return_value = "test.docx"
    mock_s3.head_object.return_value = {"ContentLength": 5000}  # No ETag!

    with patch("services.web_app.services.generation_service.get_s3_client", return_value=mock_s3):
        await _verify_output_assets(
            db=db_session,
            revision_id="rev1",
            files=[{"asset_id": asset_id, "content_hash": "client456"}],
        )

    result = await db_session.execute(select(DocumentAsset).where(DocumentAsset.id == asset_id))
    asset_after = result.scalar_one()

    assert asset_after.upload_status == "uploaded"  # 여전히 uploaded, verified 안 됨
    assert asset_after.size_bytes == 5000  # size는 업데이트됨


@pytest.mark.asyncio
async def test_verify_assets_s3_error_stays_uploaded(db_session):
    """S3 head 실패 → uploaded 유지 (graceful degradation)."""
    from unittest.mock import Mock, patch
    from services.web_app.services.generation_service import _verify_output_assets
    from services.web_app.db.models.document import DocumentAsset
    from services.web_app.db.models.base import new_cuid
    from sqlalchemy import select

    asset_id = new_cuid()
    asset = DocumentAsset(
        id=asset_id,
        org_id="org1",
        project_id="proj1",
        revision_id="rev1",
        asset_type="docx",
        storage_uri="s3://bucket/test.docx",
        upload_status="uploaded",
    )
    db_session.add(asset)
    await db_session.flush()

    # Mock S3 client - raises exception
    mock_s3 = Mock()
    mock_s3.parse_storage_uri.return_value = "test.docx"
    mock_s3.head_object.side_effect = Exception("S3 connection failed")

    with patch("services.web_app.services.generation_service.get_s3_client", return_value=mock_s3):
        # Should not raise, graceful degradation
        await _verify_output_assets(
            db=db_session,
            revision_id="rev1",
            files=[{"asset_id": asset_id, "content_hash": "client456"}],
        )

    result = await db_session.execute(select(DocumentAsset).where(DocumentAsset.id == asset_id))
    asset_after = result.scalar_one()

    assert asset_after.upload_status == "uploaded"  # 여전히 uploaded, 예외로 실패 안 함
