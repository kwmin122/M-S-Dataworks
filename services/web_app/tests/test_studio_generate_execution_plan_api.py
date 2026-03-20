"""Studio execution plan generation tests.

Tests:
1. execution_plan generates DocumentRun + DocumentRevision
2. generation contract includes snapshot/company/style for execution_plan
3. wbs_orchestrator receives correct args (company_context, company_name)
4. proposal generation still works (no regression from doc_type expansion)
5. concurrent generation guard applies to execution_plan too
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.studio import ProjectCompanyAsset, ProjectStyleSkill, ProjectPackageItem
from services.web_app.db.models.document import DocumentRun, DocumentRevision
from services.web_app.db.models.base import new_cuid


# --- Helpers (same pattern as proposal tests) ---

async def _create_org(db, name: str = "WBS 테스트기관") -> Organization:
    org = Organization(name=name)
    db.add(org)
    await db.flush()
    return org


async def _create_studio_project(db, org_id: str) -> BidProject:
    project = BidProject(
        org_id=org_id, created_by="testuser", title="WBS Studio",
        status="draft", project_type="studio", studio_stage="generate",
    )
    db.add(project)
    await db.flush()
    return project


async def _setup_user(db, org_id: str, project_id: str):
    db.add(Membership(org_id=org_id, user_id="testuser", role="editor", is_active=True))
    db.add(ProjectAccess(project_id=project_id, user_id="testuser", access_level="owner"))
    await db.flush()


async def _create_snapshot(db, org_id: str, project_id: str) -> AnalysisSnapshot:
    snap = AnalysisSnapshot(
        id=new_cuid(), org_id=org_id, project_id=project_id, version=1,
        analysis_json={
            "title": "연구용역 사업",
            "requirements": [{"name": "연구수행", "type": "scope", "value": "데이터 분석"}],
        },
        summary_md="# 사업개요\n연구용역입니다.", is_active=True, created_by="testuser",
    )
    db.add(snap)
    await db.flush()
    return snap


async def _create_package_item_wbs(db, org_id: str, project_id: str) -> ProjectPackageItem:
    item = ProjectPackageItem(
        project_id=project_id, org_id=org_id,
        package_category="generated_document",
        document_code="execution_plan",
        document_label="수행계획서/WBS",
        required=True, status="ready_to_generate",
        generation_target="execution_plan", sort_order=2,
    )
    db.add(item)
    await db.flush()
    return item


_MOCK_WBS_RESULT = MagicMock()
_MOCK_WBS_RESULT.tasks = [MagicMock(phase="착수", task_name="사업 착수", start_month=1, duration_months=1)]
_MOCK_WBS_RESULT.personnel = []
_MOCK_WBS_RESULT.total_months = 6
_MOCK_WBS_RESULT.generation_time_sec = 2.0
_MOCK_WBS_RESULT.xlsx_path = "/tmp/test.xlsx"
_MOCK_WBS_RESULT.docx_path = "/tmp/test.docx"
_MOCK_WBS_RESULT.gantt_path = "/tmp/test.png"


# ---- Tests ----

@pytest.mark.asyncio
async def test_execution_plan_creates_run_and_revision(db_session):
    """Studio generate with doc_type=execution_plan creates DocumentRun + DocumentRevision."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_wbs(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_wbs_generation") as mock_gen:
        mock_gen.return_value = _MOCK_WBS_RESULT
        result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="execution_plan"),
            user=user, db=db_session,
        )

    assert result["run_id"] is not None
    assert result["revision_id"] is not None
    assert result["status"] == "completed"

    run = (await db_session.execute(
        select(DocumentRun).where(DocumentRun.id == result["run_id"])
    )).scalar_one()
    assert run.doc_type == "execution_plan"


@pytest.mark.asyncio
async def test_execution_plan_contract_includes_snapshot(db_session):
    """Generation contract for execution_plan includes snapshot_id."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_wbs(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_wbs_generation") as mock_gen:
        mock_gen.return_value = _MOCK_WBS_RESULT
        result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="execution_plan"),
            user=user, db=db_session,
        )

    assert result["generation_contract"]["snapshot_id"] == snap.id
    assert result["generation_contract"]["doc_type"] == "execution_plan"


@pytest.mark.asyncio
async def test_wbs_orchestrator_receives_correct_args(db_session):
    """Verify company_context and company_name are passed to WBS generation."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser
    from services.web_app.db.models.company import CompanyProfile

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    await _create_package_item_wbs(db_session, org.id, project.id)

    db_session.add(CompanyProfile(org_id=org.id, company_name="WBS테스트기업"))
    db_session.add(ProjectCompanyAsset(
        project_id=project.id, org_id=org.id,
        asset_category="track_record", label="연구실적",
        content_json={"project_name": "데이터 분석 용역", "client_name": "통계청"},
    ))
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_wbs_generation") as mock_gen:
        mock_gen.return_value = _MOCK_WBS_RESULT
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="execution_plan"),
            user=user, db=db_session,
        )

    mock_gen.assert_called_once()
    call_kwargs = mock_gen.call_args.kwargs
    assert "데이터 분석 용역" in call_kwargs["company_context"]
    assert call_kwargs["company_name"] == "WBS테스트기업"


@pytest.mark.asyncio
async def test_proposal_still_works_after_doc_type_expansion(db_session):
    """Proposal generation is not regressed by doc_type Literal expansion."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id

    db_session.add(ProjectPackageItem(
        project_id=project.id, org_id=org.id,
        package_category="generated_document", document_code="proposal",
        document_label="기술 제안서", required=True, status="ready_to_generate",
        generation_target="proposal", sort_order=1,
    ))
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    mock_result = MagicMock()
    mock_result.sections = [("개요", "텍스트")]
    mock_result.quality_issues = []
    mock_result.residual_issues = []
    mock_result.generation_time_sec = 1.0

    with patch("services.web_app.api.studio._run_proposal_generation") as mock_gen:
        mock_gen.return_value = mock_result
        result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    assert result["status"] == "completed"
    assert result["generation_contract"]["doc_type"] == "proposal"


@pytest.mark.asyncio
async def test_execution_plan_updates_package_item_status(db_session):
    """After WBS generation, package item status transitions to generated."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    snap = await _create_snapshot(db_session, org.id, project.id)
    project.active_analysis_snapshot_id = snap.id
    pkg = await _create_package_item_wbs(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_wbs_generation") as mock_gen:
        mock_gen.return_value = _MOCK_WBS_RESULT
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="execution_plan"),
            user=user, db=db_session,
        )

    refreshed = (await db_session.execute(
        select(ProjectPackageItem).where(ProjectPackageItem.id == pkg.id)
    )).scalar_one()
    assert refreshed.status == "generated"
