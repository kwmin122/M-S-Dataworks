"""Layer 4: API Scenario Tests — Full lifecycle, IDOR prevention, ACL enforcement."""
from __future__ import annotations

import pytest
from services.web_app.api.adapter import SessionAdapter
from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess
from sqlalchemy import select


# --- Realistic dummy data ---
REALISTIC_RFP = {
    "title": "2026년 XX교육청 학사행정시스템 고도화 사업",
    "issuing_org": "XX교육청",
    "budget": "8억5천만원",
    "project_period": "2026-06 ~ 2027-05 (12개월)",
    "evaluation_criteria": [
        {"category": "사업 이해도", "max_score": 15, "description": "사업 배경 및 목적 이해"},
        {"category": "기술적 접근방안", "max_score": 30, "description": "시스템 아키텍처, 구현방안"},
        {"category": "수행관리 방안", "max_score": 15, "description": "일정관리, 품질관리, 리스크관리"},
        {"category": "투입인력 및 조직", "max_score": 10, "description": "PM/PL 구성"},
        {"category": "유사 수행실적", "max_score": 10, "description": "관련 경험"},
    ],
    "requirements": [
        {"category": "기능요건", "description": "학적관리, 성적처리, 출결관리 모듈"},
        {"category": "기술요건", "description": "클라우드 네이티브, MSA 기반 구축"},
        {"category": "보안요건", "description": "개인정보보호법 준수, ISMS 인증 수준"},
    ],
}


@pytest.mark.asyncio
async def test_full_project_lifecycle(db_session):
    """Create org -> project -> analysis -> verify state transitions."""
    org = Organization(name="MS솔루션")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="testpm", role="owner", is_active=True)
    db_session.add(member)
    await db_session.flush()

    project = BidProject(
        org_id=org.id,
        created_by="testpm",
        title=REALISTIC_RFP["title"],
        status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    access = ProjectAccess(
        project_id=project.id, user_id="testpm", access_level="owner",
    )
    db_session.add(access)
    await db_session.commit()

    adapter = SessionAdapter(db_session)
    snapshot = await adapter.save_analysis(
        project_id=project.id,
        org_id=org.id,
        analysis_json=REALISTIC_RFP,
        summary_md="## 사업개요\n학사행정시스템 고도화",
        username="testpm",
    )
    assert snapshot.version == 1

    result = await db_session.execute(
        select(BidProject).where(BidProject.id == project.id)
    )
    updated_project = result.scalar_one()
    assert updated_project.status == "ready_for_generation"
    assert updated_project.active_analysis_snapshot_id == snapshot.id


@pytest.mark.asyncio
async def test_idor_prevention(db_session):
    """User from org_A cannot access org_B's project."""
    org_a = Organization(name="A사")
    org_b = Organization(name="B사")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    project_b = BidProject(
        org_id=org_b.id, created_by="user_b", title="B사 프로젝트",
    )
    db_session.add(project_b)
    await db_session.commit()

    result = await db_session.execute(
        select(BidProject).where(
            BidProject.id == project_b.id,
            BidProject.org_id == org_a.id,
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_acl_level_enforcement(db_session):
    """Viewer cannot perform editor actions."""
    from services.web_app.api.deps import require_project_access, CurrentUser
    from fastapi import HTTPException

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="admin", title="ACL 테스트")
    db_session.add(project)
    await db_session.flush()

    access = ProjectAccess(
        project_id=project.id, user_id="viewer_user", access_level="viewer",
    )
    db_session.add(access)

    member = Membership(org_id=org.id, user_id="viewer_user", role="viewer", is_active=True)
    db_session.add(member)
    await db_session.commit()

    viewer = CurrentUser(username="viewer_user", org_id=org.id, role="viewer")

    await require_project_access(project.id, "viewer", viewer, db_session)

    with pytest.raises(HTTPException) as exc_info:
        await require_project_access(project.id, "editor", viewer, db_session)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_org_owner_bypasses_project_access(db_session):
    """Org owner can access any project without ProjectAccess row."""
    from services.web_app.api.deps import require_project_access, CurrentUser

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="other_user", title="타인 프로젝트")
    db_session.add(project)
    await db_session.commit()

    org_owner = CurrentUser(username="org_owner", org_id=org.id, role="owner")

    result = await require_project_access(project.id, "owner", org_owner, db_session)
    assert result is None


@pytest.mark.asyncio
async def test_org_admin_bypasses_project_access(db_session):
    """Org admin can access any project without ProjectAccess row."""
    from services.web_app.api.deps import require_project_access, CurrentUser

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="other_user", title="타인 프로젝트")
    db_session.add(project)
    await db_session.commit()

    org_admin = CurrentUser(username="org_admin", org_id=org.id, role="admin")

    result = await require_project_access(project.id, "editor", org_admin, db_session)
    assert result is None


@pytest.mark.asyncio
async def test_non_admin_without_access_row_rejected(db_session):
    """Non-admin user without ProjectAccess row gets 404."""
    from services.web_app.api.deps import require_project_access, CurrentUser
    from fastapi import HTTPException

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="other_user", title="타인 프로젝트")
    db_session.add(project)
    await db_session.commit()

    editor_no_access = CurrentUser(username="no_access_user", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await require_project_access(project.id, "viewer", editor_no_access, db_session)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_project_access_unique_constraint(db_session):
    """Duplicate (project_id, user_id) pair raises IntegrityError."""
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="UniqueTest")
    db_session.add(project)
    await db_session.flush()

    a1 = ProjectAccess(project_id=project.id, user_id="u1", access_level="owner")
    db_session.add(a1)
    await db_session.commit()

    a2 = ProjectAccess(project_id=project.id, user_id="u1", access_level="editor")
    db_session.add(a2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_multi_org_membership_rejected(db_session):
    """v1: user with multiple active memberships gets 409 from resolve_org_membership."""
    from services.web_app.api.deps import resolve_org_membership, CurrentUser
    from fastapi import HTTPException

    org_a = Organization(name="A사")
    org_b = Organization(name="B사")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    m1 = Membership(org_id=org_a.id, user_id="multi_user", role="owner", is_active=True)
    m2 = Membership(org_id=org_b.id, user_id="multi_user", role="editor", is_active=True)
    db_session.add_all([m1, m2])
    await db_session.commit()

    user = CurrentUser(username="multi_user", org_id="", role="owner")
    with pytest.raises(HTTPException) as exc_info:
        await resolve_org_membership(user=user, db=db_session)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_adapter_multi_org_rejected(db_session):
    """SessionAdapter._ensure_org() also rejects multi-org (consistent with deps)."""
    import os
    from unittest.mock import patch
    from services.web_app.api.adapter import SessionAdapter

    org_a = Organization(name="A사")
    org_b = Organization(name="B사")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    m1 = Membership(org_id=org_a.id, user_id="multi_adapter_user", role="owner", is_active=True)
    m2 = Membership(org_id=org_b.id, user_id="multi_adapter_user", role="editor", is_active=True)
    db_session.add_all([m1, m2])
    await db_session.commit()

    adapter = SessionAdapter(db_session)
    with patch.dict(os.environ, {"BID_DEV_BOOTSTRAP": "true"}, clear=False):
        with pytest.raises(ValueError, match="multiple active memberships"):
            await adapter._ensure_org("multi_adapter_user")


@pytest.mark.asyncio
async def test_adapter_ensure_org_blocked_without_bootstrap(db_session):
    """SessionAdapter._ensure_org() raises without BID_DEV_BOOTSTRAP."""
    import os
    from unittest.mock import patch
    from services.web_app.api.adapter import SessionAdapter

    adapter = SessionAdapter(db_session)

    with patch.dict(os.environ, {"BID_DEV_BOOTSTRAP": "false"}, clear=False):
        with pytest.raises(ValueError, match="no org membership"):
            await adapter._ensure_org("ghost_user")


def _make_asset_stub(revision_id=None, upload_status="uploaded"):
    """Lightweight stub for check_download_policy."""
    from types import SimpleNamespace
    return SimpleNamespace(revision_id=revision_id, upload_status=upload_status)


def test_download_policy_source_uploaded_allowed():
    from services.web_app.api.assets import check_download_policy
    check_download_policy(_make_asset_stub(revision_id=None, upload_status="uploaded"))


def test_download_policy_source_verified_allowed():
    from services.web_app.api.assets import check_download_policy
    check_download_policy(_make_asset_stub(revision_id=None, upload_status="verified"))


def test_download_policy_source_presigned_rejected():
    from services.web_app.api.assets import check_download_policy
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        check_download_policy(_make_asset_stub(revision_id=None, upload_status="presigned_issued"))
    assert exc_info.value.status_code == 409


def test_download_policy_generated_requires_verified():
    from services.web_app.api.assets import check_download_policy
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        check_download_policy(_make_asset_stub(revision_id="rev_abc123", upload_status="uploaded"))
    assert exc_info.value.status_code == 409
    assert "검증" in exc_info.value.detail


def test_download_policy_generated_verified_allowed():
    from services.web_app.api.assets import check_download_policy
    check_download_policy(_make_asset_stub(revision_id="rev_abc123", upload_status="verified"))
