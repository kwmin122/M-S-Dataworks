"""Studio track record generation tests.

Tests:
1. track_record creates DocumentRun + DocumentRevision
2. generation contract includes snapshot/doc_type
3. content_json contains records_data + personnel_data
4. package item status updated
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.studio import ProjectPackageItem
from services.web_app.db.models.document import DocumentRun, DocumentRevision
from services.web_app.db.models.base import new_cuid


async def _create_org(db) -> Organization:
    org = Organization(name="실적 테스트기관")
    db.add(org)
    await db.flush()
    return org


async def _setup(db, org_id: str):
    project = BidProject(
        org_id=org_id, created_by="testuser", title="실적 Studio",
        status="draft", project_type="studio", studio_stage="generate",
    )
    db.add(project)
    await db.flush()
    db.add(Membership(org_id=org_id, user_id="testuser", role="editor", is_active=True))
    db.add(ProjectAccess(project_id=project.id, user_id="testuser", access_level="owner"))
    snap = AnalysisSnapshot(
        id=new_cuid(), org_id=org_id, project_id=project.id, version=1,
        analysis_json={"title": "IT 용역", "requirements": []},
        summary_md="# 요약", is_active=True, created_by="testuser",
    )
    db.add(snap)
    await db.flush()
    project.active_analysis_snapshot_id = snap.id
    db.add(ProjectPackageItem(
        project_id=project.id, org_id=org_id,
        package_category="generated_document", document_code="track_record",
        document_label="실적기술서", required=True, status="ready_to_generate",
        generation_target="track_record", sort_order=5,
    ))
    await db.commit()
    return project, snap


_MOCK_TR_RESULT = MagicMock()
_MOCK_TR_RESULT.track_record_count = 2
_MOCK_TR_RESULT.personnel_count = 1
_MOCK_TR_RESULT.generation_time_sec = 3.0
_MOCK_TR_RESULT.docx_path = "/tmp/test_tr.docx"
_MOCK_TR_RESULT.records_data = [
    {"project_name": "AI 플랫폼", "description": "설명", "relevance_score": 0.9},
]
_MOCK_TR_RESULT.personnel_data = [
    {"name": "홍길동", "role": "PM", "match_reason": "10년 경력"},
]


@pytest.mark.asyncio
async def test_track_record_creates_run_and_revision(db_session):
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap = await _setup(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_track_record_generation") as mock_gen:
        mock_gen.return_value = _MOCK_TR_RESULT
        result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="track_record"),
            user=user, db=db_session,
        )

    assert result["run_id"] is not None
    assert result["status"] == "completed"
    assert result["generation_contract"]["doc_type"] == "track_record"


@pytest.mark.asyncio
async def test_track_record_content_has_records_and_personnel(db_session):
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap = await _setup(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_track_record_generation") as mock_gen:
        mock_gen.return_value = _MOCK_TR_RESULT
        result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="track_record"),
            user=user, db=db_session,
        )

    rev = (await db_session.execute(
        select(DocumentRevision).where(DocumentRevision.id == result["revision_id"])
    )).scalar_one()
    content = rev.content_json
    assert "records" in content
    assert "personnel" in content
    assert len(content["records"]) >= 1


@pytest.mark.asyncio
async def test_track_record_updates_package_item(db_session):
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap = await _setup(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_track_record_generation") as mock_gen:
        mock_gen.return_value = _MOCK_TR_RESULT
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="track_record"),
            user=user, db=db_session,
        )

    pkg = (await db_session.execute(
        select(ProjectPackageItem).where(
            ProjectPackageItem.project_id == project.id,
            ProjectPackageItem.generation_target == "track_record",
        )
    )).scalar_one()
    assert pkg.status == "generated"


@pytest.mark.asyncio
async def test_track_record_current_revision_returns_records(db_session):
    """current revision for track_record returns records + personnel."""
    from services.web_app.api.studio import generate_proposal, get_current_revision, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap = await _setup(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_track_record_generation") as mock_gen:
        mock_gen.return_value = _MOCK_TR_RESULT
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="track_record"),
            user=user, db=db_session,
        )

    rev_data = await get_current_revision(
        project_id=project.id, doc_type="track_record", user=user, db=db_session,
    )

    assert rev_data["doc_type"] == "track_record"
    assert len(rev_data["records"]) >= 1
    assert rev_data["records"][0]["project_name"] == "AI 플랫폼"
    assert len(rev_data["personnel"]) >= 1
    assert rev_data["personnel"][0]["name"] == "홍길동"
