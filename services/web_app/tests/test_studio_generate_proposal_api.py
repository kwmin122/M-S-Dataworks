"""Studio proposal generation + generation contract tests.

Tests:
1. generate endpoint creates DocumentRun + DocumentRevision
2. generation contract includes snapshot_id
3. generation contract includes company context summary
4. generation contract includes pinned style id
5. generate fails without analysis snapshot
6. generate fails without studio project
7. package item status updated to 'generated' after success
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.studio import ProjectCompanyAsset, ProjectStyleSkill, ProjectPackageItem
from services.web_app.db.models.document import DocumentRun, DocumentRevision
from services.web_app.db.models.audit import AuditLog
from services.web_app.db.models.base import new_cuid


# --- Helpers ---

async def _create_org(db, name: str = "생성 테스트기관") -> Organization:
    org = Organization(name=name)
    db.add(org)
    await db.flush()
    return org


async def _create_studio_project(db, org_id: str, title: str = "생성 Studio") -> BidProject:
    project = BidProject(
        org_id=org_id, created_by="testuser", title=title,
        status="draft", project_type="studio", studio_stage="generate",
    )
    db.add(project)
    await db.flush()
    return project


async def _setup_user(db, org_id: str, project_id: str, username: str = "testuser"):
    db.add(Membership(org_id=org_id, user_id=username, role="editor", is_active=True))
    db.add(ProjectAccess(project_id=project_id, user_id=username, access_level="owner"))
    await db.flush()


async def _create_snapshot(db, org_id: str, project_id: str) -> AnalysisSnapshot:
    snap = AnalysisSnapshot(
        id=new_cuid(),
        org_id=org_id,
        project_id=project_id,
        version=1,
        analysis_json={
            "title": "테스트 사업 제안서",
            "requirements": [
                {"name": "정보보안", "type": "qualification", "value": "ISMS 인증"},
            ],
        },
        summary_md="# 사업개요\n테스트 사업입니다.",
        is_active=True,
        created_by="testuser",
    )
    db.add(snap)
    await db.flush()
    return snap


async def _create_package_item_proposal(db, org_id: str, project_id: str) -> ProjectPackageItem:
    item = ProjectPackageItem(
        project_id=project_id, org_id=org_id,
        package_category="generated_document",
        document_code="proposal",
        document_label="기술 제안서",
        required=True,
        status="ready_to_generate",
        generation_target="proposal",
        sort_order=1,
    )
    db.add(item)
    await db.flush()
    return item


async def _create_pinned_style(db, org_id: str, project_id: str) -> ProjectStyleSkill:
    skill = ProjectStyleSkill(
        project_id=project_id, org_id=org_id,
        version=1, name="테스트 스타일",
        source_type="uploaded",
        profile_md_content="# 문체 프로필\n- 경어체 사용\n- 기술 용어 중심",
        style_json={"tone": "formal"},
    )
    db.add(skill)
    await db.flush()
    return skill


# Mock the actual LLM-based proposal generation
_MOCK_PROPOSAL_RESULT = MagicMock()
_MOCK_PROPOSAL_RESULT.sections = [("개요", "테스트 개요 텍스트")]
_MOCK_PROPOSAL_RESULT.docx_path = "/tmp/test_proposal.docx"
_MOCK_PROPOSAL_RESULT.quality_issues = []
_MOCK_PROPOSAL_RESULT.residual_issues = []
_MOCK_PROPOSAL_RESULT.generation_time_sec = 1.5


# ---- Tests ----

@pytest.mark.asyncio
async def test_generate_creates_run_and_revision(db_session):
    """Studio generate endpoint creates DocumentRun + DocumentRevision."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_proposal(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation") as mock_gen:
        mock_gen.return_value = _MOCK_PROPOSAL_RESULT
        result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    assert result["run_id"] is not None
    assert result["revision_id"] is not None
    assert result["status"] == "completed"

    # Verify DB records
    run = (await db_session.execute(
        select(DocumentRun).where(DocumentRun.id == result["run_id"])
    )).scalar_one()
    assert run.doc_type == "proposal"
    assert run.status == "completed"

    revision = (await db_session.execute(
        select(DocumentRevision).where(DocumentRevision.id == result["revision_id"])
    )).scalar_one()
    assert revision.doc_type == "proposal"
    assert revision.source == "ai_generated"


@pytest.mark.asyncio
async def test_generation_contract_includes_snapshot_id(db_session):
    """Generation contract metadata includes analysis snapshot id."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_proposal(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation") as mock_gen:
        mock_gen.return_value = _MOCK_PROPOSAL_RESULT
        result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    contract = result["generation_contract"]
    assert contract["snapshot_id"] == snap.id


@pytest.mark.asyncio
async def test_generation_contract_includes_company_summary(db_session):
    """Generation contract includes company context summary."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_proposal(db_session, org.id, project.id)

    # Add company staging asset
    db_session.add(ProjectCompanyAsset(
        project_id=project.id, org_id=org.id,
        asset_category="track_record", label="테스트 실적",
        content_json={"project_name": "AI 플랫폼 구축", "client_name": "과기부"},
    ))
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation") as mock_gen:
        mock_gen.return_value = _MOCK_PROPOSAL_RESULT
        result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    contract = result["generation_contract"]
    assert contract["company_assets_count"] > 0


@pytest.mark.asyncio
async def test_generation_contract_includes_pinned_style(db_session):
    """Generation contract includes pinned style skill id."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_proposal(db_session, org.id, project.id)

    style = await _create_pinned_style(db_session, org.id, project.id)
    project.pinned_style_skill_id = style.id
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation") as mock_gen:
        mock_gen.return_value = _MOCK_PROPOSAL_RESULT
        result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    contract = result["generation_contract"]
    assert contract["pinned_style_skill_id"] == style.id
    assert contract["pinned_style_name"] == "테스트 스타일"


@pytest.mark.asyncio
async def test_generate_fails_without_snapshot(db_session):
    """Generate fails with 400 if no analysis snapshot."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_generate_fails_non_studio_project(db_session):
    """Generate fails on non-studio project."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    chat = BidProject(
        org_id=org.id, created_by="testuser", title="Chat",
        status="draft", project_type="chat",
    )
    db_session.add(chat)
    await db_session.flush()
    await _setup_user(db_session, org.id, chat.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await generate_proposal(
            project_id=chat.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_generate_creates_audit_log(db_session):
    """Generate creates AuditLog."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_proposal(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation") as mock_gen:
        mock_gen.return_value = _MOCK_PROPOSAL_RESULT
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    logs = (await db_session.execute(
        select(AuditLog).where(
            AuditLog.project_id == project.id,
            AuditLog.action == "proposal_generated",
        )
    )).scalars().all()
    assert len(logs) >= 1


# ---- Hardening tests: orchestrator args, revision read, company_name ----

@pytest.mark.asyncio
async def test_orchestrator_receives_correct_args(db_session):
    """Mock args verification: company_context, style_profile_md, total_pages, company_name."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser
    from services.web_app.db.models.company import CompanyProfile

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_proposal(db_session, org.id, project.id)

    # Company profile
    db_session.add(CompanyProfile(
        org_id=org.id, company_name="테스트기업 주식회사", business_type="IT",
    ))

    # Staging asset
    db_session.add(ProjectCompanyAsset(
        project_id=project.id, org_id=org.id,
        asset_category="track_record", label="AI 플랫폼",
        content_json={"project_name": "AI 플랫폼 구축", "client_name": "과기부"},
    ))

    # Pin style
    style = await _create_pinned_style(db_session, org.id, project.id)
    project.pinned_style_skill_id = style.id
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation") as mock_gen:
        mock_gen.return_value = _MOCK_PROPOSAL_RESULT
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal", total_pages=80),
            user=user, db=db_session,
        )

    mock_gen.assert_called_once()
    call_kwargs = mock_gen.call_args.kwargs

    # company_context should include staging asset
    assert "AI 플랫폼 구축" in call_kwargs["company_context"]
    # style profile should be from pinned style
    assert "경어체 사용" in call_kwargs["style_profile_md"]
    # total_pages forwarded
    assert call_kwargs["total_pages"] == 80
    # company_name propagated
    assert call_kwargs["company_name"] == "테스트기업 주식회사"


@pytest.mark.asyncio
async def test_read_current_revision(db_session):
    """GET current revision returns sections content after generation."""
    from services.web_app.api.studio import generate_proposal, get_current_revision, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_proposal(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation") as mock_gen:
        mock_gen.return_value = _MOCK_PROPOSAL_RESULT
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    # Read current revision
    revision_data = await get_current_revision(
        project_id=project.id, doc_type="proposal", user=user, db=db_session,
    )

    assert revision_data["revision_number"] >= 1
    assert revision_data["source"] == "ai_generated"
    assert len(revision_data["sections"]) >= 1
    assert revision_data["sections"][0]["name"] == "개요"


@pytest.mark.asyncio
async def test_company_name_absent_passes_none(db_session):
    """When no CompanyProfile exists, company_name=None is passed to orchestrator."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_proposal(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation") as mock_gen:
        mock_gen.return_value = _MOCK_PROPOSAL_RESULT
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    call_kwargs = mock_gen.call_args.kwargs
    assert call_kwargs["company_name"] is None
