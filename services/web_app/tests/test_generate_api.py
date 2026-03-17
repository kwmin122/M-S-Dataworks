"""Core tests for /api/projects/{id}/generate endpoint."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch
from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.company import CompanyProfile
from services.web_app.db.models.document import DocumentRun, DocumentRevision, DocumentAsset
from sqlalchemy import select


@pytest.mark.asyncio
async def test_generate_happy_path(db_session):
    """Happy path: 200 + revision_id + output_files."""
    # Setup: org, member, project, snapshot, profile
    org = Organization(name="테스트회사")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="user1", role="editor", is_active=True)
    db_session.add(member)

    project = BidProject(
        org_id=org.id,
        created_by="user1",
        title="테스트 사업",
        status="ready_for_generation",
    )
    db_session.add(project)
    await db_session.flush()

    snapshot = AnalysisSnapshot(
        org_id=org.id,
        project_id=project.id,
        version=1,
        analysis_json={"title": "테스트 RFP", "requirements": []},
        is_active=True,
    )
    db_session.add(snapshot)
    await db_session.flush()

    project.active_analysis_snapshot_id = snapshot.id
    await db_session.commit()

    profile = CompanyProfile(org_id=org.id, company_name="테스트회사")
    db_session.add(profile)

    # Add ProjectAccess for editor permission
    access = ProjectAccess(
        project_id=project.id,
        user_id="user1",
        access_level="editor",
    )
    db_session.add(access)
    await db_session.commit()

    # Mock S3 client
    mock_s3 = Mock()
    mock_s3.generate_presigned_upload_url.return_value = "https://s3.mock/presigned-url"
    mock_s3.build_full_uri.return_value = "s3://test-bucket/test-key"

    # Mock rag_engine success — use actual asset_id from upload_targets
    def mock_rag_engine(**kwargs):
        upload_targets = kwargs.get("upload_targets", [])
        asset_id = upload_targets[0]["asset_id"] if upload_targets else "fallback_asset"
        return {
            "doc_type": "proposal",
            "content_json": {"sections": [{"name": "개요", "text": "내용"}]},
            "content_schema": "proposal_sections_v1",
            "output_files": [
                {"asset_id": asset_id, "asset_type": "docx", "size_bytes": 1000, "content_hash": "hash1"}
            ],
            "generation_time_sec": 10.5,
        }

    with patch("services.web_app.api.generate.get_s3_client", return_value=mock_s3), \
         patch("services.web_app.api.generate._call_rag_engine_generate", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = mock_rag_engine

        # Act: Call endpoint (would be via TestClient in real integration test)
        from services.web_app.api.generate import generate_document
        from services.web_app.api.deps import CurrentUser
        from services.web_app.api.generate import GenerateDocumentProjectRequest

        user = CurrentUser(username="user1", org_id=org.id, role="editor")
        request = GenerateDocumentProjectRequest(
            doc_type="proposal",
            analysis_snapshot_id=snapshot.id,
            params={},
        )

        response = await generate_document(
            project_id=project.id,
            request=request,
            user=user,
            db=db_session,
        )

    # Assert: 200 response
    assert response.status == "completed"
    assert response.doc_type == "proposal"
    assert len(response.output_files) > 0

    # Assert: DB state - DocumentRun created and completed
    result = await db_session.execute(
        select(DocumentRun).where(DocumentRun.project_id == project.id)
    )
    run = result.scalar_one()
    assert run.status == "completed"
    assert run.doc_type == "proposal"

    # Assert: DocumentRevision created
    result = await db_session.execute(
        select(DocumentRevision).where(DocumentRevision.run_id == run.id)
    )
    revision = result.scalar_one()
    assert revision.status == "draft"
    assert revision.source == "ai_generated"

    # Assert: DocumentAsset linked to revision + upload_status transitioned
    result = await db_session.execute(
        select(DocumentAsset).where(
            DocumentAsset.project_id == project.id,
            DocumentAsset.revision_id == revision.id,
        )
    )
    assets = result.scalars().all()
    assert len(assets) > 0, "Should have assets linked to revision"
    for asset in assets:
        assert asset.revision_id == revision.id, f"Asset {asset.id} not linked to revision"
        # upload_status should be "uploaded" or "verified" (not "presigned_issued" or "failed")
        assert asset.upload_status in ("uploaded", "verified"), \
            f"Asset {asset.id} status={asset.upload_status}, expected uploaded/verified"


@pytest.mark.asyncio
async def test_generate_acl_deny(db_session):
    """ACL deny: user lacks project access → 404."""
    # Setup: org, project (no ProjectAccess for user)
    org = Organization(name="테스트회사")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="user1", role="viewer", is_active=True)
    db_session.add(member)

    project = BidProject(
        org_id=org.id,
        created_by="other_user",
        title="비공개 사업",
        status="ready_for_generation",
    )
    db_session.add(project)
    await db_session.commit()

    # No ProjectAccess row for user1, and user is not owner/admin

    # Act: Call endpoint
    from services.web_app.api.generate import generate_document
    from services.web_app.api.deps import CurrentUser
    from services.web_app.api.generate import GenerateDocumentProjectRequest
    from fastapi import HTTPException

    user = CurrentUser(username="user1", org_id=org.id, role="viewer")
    request = GenerateDocumentProjectRequest(doc_type="proposal", params={})

    # Assert: 404 (require_project_access should raise)
    with pytest.raises(HTTPException) as exc_info:
        await generate_document(
            project_id=project.id,
            request=request,
            user=user,
            db=db_session,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_generate_no_snapshot(db_session):
    """No snapshot: project without analysis → 400."""
    # Setup: org, project (no active_analysis_snapshot_id)
    org = Organization(name="테스트회사")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="user1", role="owner", is_active=True)
    db_session.add(member)

    project = BidProject(
        org_id=org.id,
        created_by="user1",
        title="분석 안 된 사업",
        status="collecting_inputs",
        active_analysis_snapshot_id=None,  # No snapshot!
    )
    db_session.add(project)
    await db_session.commit()

    # Act: Call endpoint
    from services.web_app.api.generate import generate_document
    from services.web_app.api.deps import CurrentUser
    from services.web_app.api.generate import GenerateDocumentProjectRequest
    from fastapi import HTTPException

    user = CurrentUser(username="user1", org_id=org.id, role="owner")
    request = GenerateDocumentProjectRequest(doc_type="proposal", params={})

    # Assert: 400 (no analysis snapshot)
    with pytest.raises(HTTPException) as exc_info:
        await generate_document(
            project_id=project.id,
            request=request,
            user=user,
            db=db_session,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_generate_rag_engine_error(db_session):
    """rag_engine error: upstream failure → 502 + DocumentRun.status=failed."""
    # Setup: org, project, snapshot
    org = Organization(name="테스트회사")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="user1", role="owner", is_active=True)
    db_session.add(member)

    project = BidProject(
        org_id=org.id,
        created_by="user1",
        title="테스트 사업",
        status="ready_for_generation",
    )
    db_session.add(project)
    await db_session.flush()

    snapshot = AnalysisSnapshot(
        org_id=org.id,
        project_id=project.id,
        version=1,
        analysis_json={"title": "테스트 RFP", "requirements": []},
        is_active=True,
    )
    db_session.add(snapshot)
    await db_session.flush()

    project.active_analysis_snapshot_id = snapshot.id
    await db_session.commit()

    # Mock S3 client
    mock_s3 = Mock()
    mock_s3.generate_presigned_upload_url.return_value = "https://s3.mock/presigned-url"
    mock_s3.build_full_uri.return_value = "s3://test-bucket/test-key"

    # Mock rag_engine error
    with patch("services.web_app.api.generate.get_s3_client", return_value=mock_s3), \
         patch("services.web_app.api.generate._call_rag_engine_generate", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = Exception("LLM timeout")

        # Act: Call endpoint
        from services.web_app.api.generate import generate_document
        from services.web_app.api.deps import CurrentUser
        from services.web_app.api.generate import GenerateDocumentProjectRequest
        from fastapi import HTTPException

        user = CurrentUser(username="user1", org_id=org.id, role="owner")
        request = GenerateDocumentProjectRequest(doc_type="proposal", params={})

        # Assert: 502 Bad Gateway
        with pytest.raises(HTTPException) as exc_info:
            await generate_document(
                project_id=project.id,
                request=request,
                user=user,
                db=db_session,
            )
        assert exc_info.value.status_code == 502

    # Assert: DB state - DocumentRun exists with status=failed
    result = await db_session.execute(
        select(DocumentRun).where(DocumentRun.project_id == project.id)
    )
    run = result.scalar_one()
    assert run.status == "failed"
    assert "LLM timeout" in run.error_message

    # Assert: Orphan assets marked failed
    result = await db_session.execute(
        select(DocumentAsset).where(DocumentAsset.project_id == project.id)
    )
    assets = result.scalars().all()
    assert len(assets) > 0, "Should have pre-created assets"
    for asset in assets:
        assert asset.upload_status == "failed", f"Asset {asset.id} not marked failed"


@pytest.mark.asyncio
async def test_generate_rag_engine_timeout_and_asset_cleanup(db_session):
    """rag_engine timeout: 504 + assets marked failed."""
    # Setup: org, project, snapshot
    org = Organization(name="테스트회사")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="user1", role="owner", is_active=True)
    db_session.add(member)

    project = BidProject(
        org_id=org.id,
        created_by="user1",
        title="테스트 사업",
        status="ready_for_generation",
    )
    db_session.add(project)
    await db_session.flush()

    snapshot = AnalysisSnapshot(
        org_id=org.id,
        project_id=project.id,
        version=1,
        analysis_json={"title": "테스트 RFP", "requirements": []},
        is_active=True,
    )
    db_session.add(snapshot)
    await db_session.flush()

    project.active_analysis_snapshot_id = snapshot.id
    await db_session.commit()

    # Mock S3 client
    mock_s3 = Mock()
    mock_s3.generate_presigned_upload_url.return_value = "https://s3.mock/presigned-url"
    mock_s3.build_full_uri.return_value = "s3://test-bucket/test-key"

    # Mock rag_engine timeout
    import asyncio
    with patch("services.web_app.api.generate.get_s3_client", return_value=mock_s3), \
         patch("services.web_app.api.generate._call_rag_engine_generate", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = asyncio.TimeoutError("rag_engine timeout")

        # Act: Call endpoint
        from services.web_app.api.generate import generate_document
        from services.web_app.api.deps import CurrentUser
        from services.web_app.api.generate import GenerateDocumentProjectRequest
        from fastapi import HTTPException

        user = CurrentUser(username="user1", org_id=org.id, role="owner")
        request = GenerateDocumentProjectRequest(doc_type="proposal", params={})

        # Assert: 504 Gateway Timeout
        with pytest.raises(HTTPException) as exc_info:
            await generate_document(
                project_id=project.id,
                request=request,
                user=user,
                db=db_session,
            )
        assert exc_info.value.status_code == 504

    # Assert: DB state - DocumentRun failed
    result = await db_session.execute(
        select(DocumentRun).where(DocumentRun.project_id == project.id)
    )
    run = result.scalar_one()
    assert run.status == "failed"

    # Assert: Pre-created assets are marked failed (orphan cleanup)
    result = await db_session.execute(
        select(DocumentAsset).where(DocumentAsset.project_id == project.id)
    )
    assets = result.scalars().all()
    # If assets were pre-created, they should now be failed
    # (This assumes implementation pre-creates assets in Phase 1)
    for asset in assets:
        assert asset.upload_status == "failed"
