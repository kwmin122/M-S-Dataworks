"""Proposal review/relearn end-to-end tests.

Loop: generate → edit → diff → relearn (derive style) → repin → regenerate → verify change.

Tests:
1. save edited proposal creates new revision (source=user_edited)
2. diff returns section-level changes + edit_rate
3. relearn creates new project-scoped style skill (derived)
4. shared default unchanged after relearn
5. repin to new skill works
6. regenerate with new style changes contract + section text
7. no-access rejected
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.studio import ProjectStyleSkill, ProjectPackageItem
from services.web_app.db.models.document import DocumentRevision
from services.web_app.db.models.base import new_cuid


# --- Helpers ---

async def _create_org(db) -> Organization:
    org = Organization(name="리런 테스트기관")
    db.add(org)
    await db.flush()
    return org


async def _full_setup(db, org_id: str):
    """Create project + snapshot + style + package item + initial generation."""
    project = BidProject(
        org_id=org_id, created_by="testuser", title="리런 Studio",
        status="draft", project_type="studio", studio_stage="review",
    )
    db.add(project)
    await db.flush()
    db.add(Membership(org_id=org_id, user_id="testuser", role="editor", is_active=True))
    db.add(ProjectAccess(project_id=project.id, user_id="testuser", access_level="owner"))

    snap = AnalysisSnapshot(
        id=new_cuid(), org_id=org_id, project_id=project.id, version=1,
        analysis_json={"title": "테스트 사업", "requirements": []},
        summary_md="# 요약", is_active=True, created_by="testuser",
    )
    db.add(snap)
    await db.flush()
    project.active_analysis_snapshot_id = snap.id

    style = ProjectStyleSkill(
        project_id=project.id, org_id=org_id, version=1,
        name="원본 스타일", source_type="uploaded",
        profile_md_content="# 원본 프로필\n- 경어체 사용",
    )
    db.add(style)
    await db.flush()
    project.pinned_style_skill_id = style.id

    db.add(ProjectPackageItem(
        project_id=project.id, org_id=org_id,
        package_category="generated_document", document_code="proposal",
        document_label="기술 제안서", required=True, status="ready_to_generate",
        generation_target="proposal", sort_order=1,
    ))
    await db.commit()
    return project, snap, style


def _mock_gen_by_style(rfx_result, company_context, style_profile_md, total_pages, company_name=None):
    """Mock that returns different sections based on style_profile_md content."""
    result = MagicMock()
    if "수정됨" in (style_profile_md or ""):
        result.sections = [("개요", "수정 스타일 반영된 개요 텍스트"), ("본론", "수정 본론")]
    else:
        result.sections = [("개요", "원본 스타일 기반 개요 텍스트"), ("본론", "원본 본론")]
    result.quality_issues = []
    result.residual_issues = []
    result.generation_time_sec = 1.0
    return result


# ---- Tests ----

@pytest.mark.asyncio
async def test_save_edited_proposal(db_session):
    """Save edited sections creates new revision with source=user_edited."""
    from services.web_app.api.studio import generate_proposal, save_edited_proposal, GenerateProposalRequest, SaveEditedProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap, style = await _full_setup(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # Generate first
    with patch("services.web_app.api.studio._run_proposal_generation", side_effect=_mock_gen_by_style):
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    # Save edited
    result = await save_edited_proposal(
        project_id=project.id,
        req=SaveEditedProposalRequest(
            sections=[
                {"name": "개요", "text": "사용자가 수정한 개요"},
                {"name": "본론", "text": "원본 본론"},
            ],
        ),
        user=user, db=db_session,
    )

    assert result["source"] == "user_edited"
    assert result["revision_number"] == 2

    rev = (await db_session.execute(
        select(DocumentRevision).where(DocumentRevision.id == result["revision_id"])
    )).scalar_one()
    assert rev.source == "user_edited"
    assert rev.content_json["sections"][0]["text"] == "사용자가 수정한 개요"


@pytest.mark.asyncio
async def test_proposal_diff(db_session):
    """Diff returns section-level changes and edit_rate."""
    from services.web_app.api.studio import generate_proposal, save_edited_proposal, get_proposal_diff, GenerateProposalRequest, SaveEditedProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap, style = await _full_setup(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation", side_effect=_mock_gen_by_style):
        gen_result = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    await save_edited_proposal(
        project_id=project.id,
        req=SaveEditedProposalRequest(
            sections=[
                {"name": "개요", "text": "사용자가 수정한 개요 텍스트"},
                {"name": "본론", "text": "원본 본론"},
            ],
        ),
        user=user, db=db_session,
    )

    diff = await get_proposal_diff(
        project_id=project.id, user=user, db=db_session,
    )

    assert diff["changed_sections_count"] >= 1
    assert 0 < diff["edit_rate"] <= 1.0
    assert len(diff["sections"]) == 2
    # "개요" should be marked as changed
    changed = [s for s in diff["sections"] if s["changed"]]
    assert len(changed) >= 1


@pytest.mark.asyncio
async def test_relearn_creates_derived_style(db_session):
    """Relearn creates new project-scoped style skill with source_type=derived."""
    from services.web_app.api.studio import generate_proposal, save_edited_proposal, relearn_proposal_style, GenerateProposalRequest, SaveEditedProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap, style = await _full_setup(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with patch("services.web_app.api.studio._run_proposal_generation", side_effect=_mock_gen_by_style):
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    await save_edited_proposal(
        project_id=project.id,
        req=SaveEditedProposalRequest(
            sections=[{"name": "개요", "text": "수정됨 개요"}, {"name": "본론", "text": "수정됨 본론"}],
        ),
        user=user, db=db_session,
    )

    result = await relearn_proposal_style(
        project_id=project.id, user=user, db=db_session,
    )

    assert result["new_skill_id"] is not None
    assert result["derived_from_id"] == style.id

    new_skill = (await db_session.execute(
        select(ProjectStyleSkill).where(ProjectStyleSkill.id == result["new_skill_id"])
    )).scalar_one()
    assert new_skill.source_type == "derived"
    assert new_skill.project_id == project.id
    assert "수정" in (new_skill.profile_md_content or "")


@pytest.mark.asyncio
async def test_shared_default_unchanged_after_relearn(db_session):
    """Relearn does not modify shared default style."""
    from services.web_app.api.studio import generate_proposal, save_edited_proposal, relearn_proposal_style, promote_style_skill, GenerateProposalRequest, SaveEditedProposalRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap, style = await _full_setup(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # Promote to shared first
    await promote_style_skill(project_id=project.id, skill_id=style.id, user=user, db=db_session)

    shared_before = (await db_session.execute(
        select(ProjectStyleSkill).where(
            ProjectStyleSkill.org_id == org.id,
            ProjectStyleSkill.is_shared_default == True,
        )
    )).scalar_one()
    shared_profile_before = shared_before.profile_md_content

    # Generate + edit + relearn
    with patch("services.web_app.api.studio._run_proposal_generation", side_effect=_mock_gen_by_style):
        await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    await save_edited_proposal(
        project_id=project.id,
        req=SaveEditedProposalRequest(
            sections=[{"name": "개요", "text": "수정됨"}, {"name": "본론", "text": "수정됨"}],
        ),
        user=user, db=db_session,
    )
    await relearn_proposal_style(project_id=project.id, user=user, db=db_session)

    # Shared default must be unchanged
    shared_after = (await db_session.execute(
        select(ProjectStyleSkill).where(ProjectStyleSkill.id == shared_before.id)
    )).scalar_one()
    assert shared_after.profile_md_content == shared_profile_before
    assert shared_after.is_shared_default is True


@pytest.mark.asyncio
async def test_full_relearn_loop_changes_output(db_session):
    """Full loop: generate → edit → relearn → repin → regenerate → verify change."""
    from services.web_app.api.studio import (
        generate_proposal, save_edited_proposal, relearn_proposal_style,
        pin_style_skill, GenerateProposalRequest, SaveEditedProposalRequest,
    )
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project, snap, style = await _full_setup(db_session, org.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # 1. Generate with original style
    with patch("services.web_app.api.studio._run_proposal_generation", side_effect=_mock_gen_by_style):
        gen1 = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    original_contract = gen1["generation_contract"]
    original_skill_id = original_contract["pinned_style_skill_id"]

    # 2. Edit (include "수정됨" to trigger different output)
    await save_edited_proposal(
        project_id=project.id,
        req=SaveEditedProposalRequest(
            sections=[{"name": "개요", "text": "수정됨 개요"}, {"name": "본론", "text": "수정됨 본론"}],
        ),
        user=user, db=db_session,
    )

    # 3. Relearn
    relearn_result = await relearn_proposal_style(
        project_id=project.id, user=user, db=db_session,
    )
    new_skill_id = relearn_result["new_skill_id"]

    # 4. Repin to new skill
    await pin_style_skill(
        project_id=project.id, skill_id=new_skill_id, user=user, db=db_session,
    )

    # 5. Regenerate
    with patch("services.web_app.api.studio._run_proposal_generation", side_effect=_mock_gen_by_style):
        gen2 = await generate_proposal(
            project_id=project.id,
            req=GenerateProposalRequest(doc_type="proposal"),
            user=user, db=db_session,
        )

    # VERIFY: contract skill changed
    new_contract = gen2["generation_contract"]
    assert new_contract["pinned_style_skill_id"] != original_skill_id
    assert new_contract["pinned_style_skill_id"] == new_skill_id

    # VERIFY: at least 1 section text differs
    rev1 = (await db_session.execute(
        select(DocumentRevision).where(DocumentRevision.id == gen1["revision_id"])
    )).scalar_one()
    rev2 = (await db_session.execute(
        select(DocumentRevision).where(DocumentRevision.id == gen2["revision_id"])
    )).scalar_one()

    sections1 = {s["name"]: s["text"] for s in rev1.content_json["sections"]}
    sections2 = {s["name"]: s["text"] for s in rev2.content_json["sections"]}
    changed = [name for name in sections1 if sections1.get(name) != sections2.get(name)]
    assert len(changed) >= 1, f"Expected at least 1 changed section, got {changed}"


@pytest.mark.asyncio
async def test_relearn_no_access_rejected(db_session):
    """No-access user rejected."""
    from services.web_app.api.studio import relearn_proposal_style
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    project, _, _ = await _full_setup(db_session, org.id)
    db_session.add(Membership(org_id=org.id, user_id="outsider", role="editor", is_active=True))
    await db_session.flush()

    outsider = CurrentUser(username="outsider", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await relearn_proposal_style(project_id=project.id, user=outsider, db=db_session)
    assert exc_info.value.status_code == 404
