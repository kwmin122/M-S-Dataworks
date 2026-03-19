"""Studio presentation (PPT) generation tests.

Tests:
1. presentation creates run + revision with slides/qna in content_json
2. generation contract includes proposal/exec revision ids + degraded_inputs
3. .pptx asset created and linked
4. fallback without proposal revision
5. fallback without execution_plan revision
6. PPT-specific request params (target_slide_count, duration_min, qna_count)
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.studio import ProjectPackageItem
from services.web_app.db.models.document import DocumentRun, DocumentRevision, DocumentAsset, ProjectCurrentDocument
from services.web_app.db.models.base import new_cuid


async def _create_org(db) -> Organization:
    org = Organization(name="PPT 테스트기관")
    db.add(org)
    await db.flush()
    return org


async def _setup_project(db, org_id: str):
    project = BidProject(
        org_id=org_id, created_by="testuser", title="PPT Studio",
        status="draft", project_type="studio", studio_stage="generate",
    )
    db.add(project)
    await db.flush()
    db.add(Membership(org_id=org_id, user_id="testuser", role="editor", is_active=True))
    db.add(ProjectAccess(project_id=project.id, user_id="testuser", access_level="owner"))

    snap = AnalysisSnapshot(
        id=new_cuid(), org_id=org_id, project_id=project.id, version=1,
        analysis_json={"title": "IT 용역 사업", "requirements": [{"name": "보안", "type": "qualification"}]},
        summary_md="# 사업개요", is_active=True, created_by="testuser",
    )
    db.add(snap)
    await db.flush()
    project.active_analysis_snapshot_id = snap.id

    db.add(ProjectPackageItem(
        project_id=project.id, org_id=org_id,
        package_category="generated_document", document_code="presentation",
        document_label="발표자료", required=True, status="ready_to_generate",
        generation_target="presentation", sort_order=3,
    ))
    await db.commit()
    return project, snap


async def _create_proposal_revision(db, org_id: str, project_id: str):
    """Create a proposal revision to feed into PPT."""
    rev = DocumentRevision(
        org_id=org_id, project_id=project_id, doc_type="proposal",
        revision_number=1, source="ai_generated", status="draft",
        title="테스트 제안서",
        content_json={"sections": [
            {"name": "개요", "text": "사업 개요 텍스트"},
            {"name": "전략", "text": "제안 전략 텍스트"},
        ]},
        content_schema="proposal_sections_v1", created_by="testuser",
    )
    db.add(rev)
    await db.flush()
    db.add(ProjectCurrentDocument(
        org_id=org_id, project_id=project_id,
        doc_type="proposal", current_revision_id=rev.id,
    ))
    await db.commit()
    return rev


async def _create_exec_plan_revision(db, org_id: str, project_id: str):
    """Create an execution_plan revision to feed into PPT."""
    rev = DocumentRevision(
        org_id=org_id, project_id=project_id, doc_type="execution_plan",
        revision_number=1, source="ai_generated", status="draft",
        title="수행계획서",
        content_json={"sections": [
            {"name": "착수", "text": "착수 단계"},
            {"name": "분석", "text": "분석 단계"},
        ]},
        content_schema="execution_plan_tasks_v1", created_by="testuser",
    )
    db.add(rev)
    await db.flush()
    db.add(ProjectCurrentDocument(
        org_id=org_id, project_id=project_id,
        doc_type="execution_plan", current_revision_id=rev.id,
    ))
    await db.commit()
    return rev


def _mock_ppt_result():
    from unittest.mock import MagicMock
    qna1 = MagicMock()
    qna1.question = "보안 방안은?"
    qna1.answer = "ISMS 인증 기반"
    qna1.category = "기술"
    qna2 = MagicMock()
    qna2.question = "일정 리스크는?"
    qna2.answer = "마일스톤 관리"
    qna2.category = "관리"

    result = MagicMock()
    result.pptx_path = "/tmp/test_presentation.pptx"
    result.slide_count = 15
    result.qna_pairs = [qna1, qna2]
    result.total_duration_min = 25.0
    result.generation_time_sec = 5.0
    result.slides_metadata = [
        {"slide_type": "cover", "title": "IT 용역 사업 제안"},
        {"slide_type": "content", "title": "사업 이해"},
        {"slide_type": "content", "title": "제안 전략"},
    ]
    return result


@pytest.mark.asyncio
async def test_presentation_creates_run_and_revision(db_session, tmp_path):
    """PPT generation creates DocumentRun + revision with slides/qna."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap = await _setup_project(db_session, org.id)
    await _create_proposal_revision(db_session, org.id, project.id)
    await _create_exec_plan_revision(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    mock_result = _mock_ppt_result()
    # Create the fake pptx file
    import os
    os.makedirs(os.path.dirname(mock_result.pptx_path), exist_ok=True)
    with open(mock_result.pptx_path, "wb") as f:
        f.write(b"fake pptx content")

    with patch("services.web_app.api.studio._run_ppt_generation") as mock_gen:
        mock_gen.return_value = mock_result
        with patch("services.web_app.api.studio._PPT_ASSET_DIR", str(tmp_path)):
            result = await generate_proposal(
                project_id=project.id,
                req=GenerateProposalRequest(doc_type="presentation", target_slide_count=15, duration_min=25, qna_count=10),
                user=user, db=db_session,
            )

    assert result["run_id"] is not None
    assert result["status"] == "completed"

    rev = (await db_session.execute(
        select(DocumentRevision).where(DocumentRevision.id == result["revision_id"])
    )).scalar_one()
    assert rev.doc_type == "presentation"
    content = rev.content_json
    assert "slides" in content
    assert "qna_pairs" in content
    assert len(content["slides"]) >= 1
    assert len(content["qna_pairs"]) >= 1


@pytest.mark.asyncio
async def test_presentation_contract_includes_revision_ids(db_session, tmp_path):
    """Contract includes proposal_revision_id and execution_plan_revision_id."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap = await _setup_project(db_session, org.id)
    prop_rev = await _create_proposal_revision(db_session, org.id, project.id)
    exec_rev = await _create_exec_plan_revision(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    mock_result = _mock_ppt_result()
    import os
    os.makedirs(os.path.dirname(mock_result.pptx_path), exist_ok=True)
    with open(mock_result.pptx_path, "wb") as f:
        f.write(b"fake pptx")

    with patch("services.web_app.api.studio._run_ppt_generation") as mock_gen:
        mock_gen.return_value = mock_result
        with patch("services.web_app.api.studio._PPT_ASSET_DIR", str(tmp_path)):
            result = await generate_proposal(
                project_id=project.id,
                req=GenerateProposalRequest(doc_type="presentation"),
                user=user, db=db_session,
            )

    contract = result["generation_contract"]
    assert contract["proposal_revision_id"] == prop_rev.id
    assert contract["execution_plan_revision_id"] == exec_rev.id
    assert contract["doc_type"] == "presentation"
    assert "degraded_inputs" in contract


@pytest.mark.asyncio
async def test_presentation_without_proposal_fallback(db_session, tmp_path):
    """PPT generates even without proposal revision (degraded mode)."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap = await _setup_project(db_session, org.id)
    # No proposal revision
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    mock_result = _mock_ppt_result()
    import os
    os.makedirs(os.path.dirname(mock_result.pptx_path), exist_ok=True)
    with open(mock_result.pptx_path, "wb") as f:
        f.write(b"fake")

    with patch("services.web_app.api.studio._run_ppt_generation") as mock_gen:
        mock_gen.return_value = mock_result
        with patch("services.web_app.api.studio._PPT_ASSET_DIR", str(tmp_path)):
            result = await generate_proposal(
                project_id=project.id,
                req=GenerateProposalRequest(doc_type="presentation"),
                user=user, db=db_session,
            )

    assert result["status"] == "completed"
    contract = result["generation_contract"]
    assert contract["proposal_revision_id"] is None
    assert contract["degraded_inputs"]["proposal"] is False


@pytest.mark.asyncio
async def test_presentation_pptx_asset_created(db_session, tmp_path):
    """.pptx file copied to asset dir and DocumentAsset created."""
    from services.web_app.api.studio import generate_proposal, GenerateProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap = await _setup_project(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    mock_result = _mock_ppt_result()
    import os
    os.makedirs(os.path.dirname(mock_result.pptx_path), exist_ok=True)
    with open(mock_result.pptx_path, "wb") as f:
        f.write(b"pptx bytes here")

    with patch("services.web_app.api.studio._run_ppt_generation") as mock_gen:
        mock_gen.return_value = mock_result
        with patch("services.web_app.api.studio._PPT_ASSET_DIR", str(tmp_path)):
            result = await generate_proposal(
                project_id=project.id,
                req=GenerateProposalRequest(doc_type="presentation"),
                user=user, db=db_session,
            )

    # Verify DocumentAsset created
    assets = (await db_session.execute(
        select(DocumentAsset).where(
            DocumentAsset.project_id == project.id,
            DocumentAsset.asset_type == "pptx",
        )
    )).scalars().all()
    assert len(assets) >= 1
    assert assets[0].original_filename.endswith(".pptx")
