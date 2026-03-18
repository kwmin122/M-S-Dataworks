"""Style Skill pin / derive / promote tests for Studio projects.

Tests:
1. create_style_skill creates a project-scoped style skill row
2. pin updates bid_projects.pinned_style_skill_id
3. list returns project-scoped + shared default skills
4. derive creates v2 referencing v1 via derived_from_id
5. promote creates org-level shared default (project_id=NULL, is_shared_default=True)
6. promote preserves derive lineage
7. only one shared default per org (second promote replaces first)
8. non-studio project rejected
9. non-access user rejected
10. unpin clears pinned_style_skill_id
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess
from services.web_app.db.models.studio import ProjectStyleSkill
from services.web_app.db.models.audit import AuditLog


# --- Helpers ---

async def _create_org(db, name: str = "스타일 테스트기관") -> Organization:
    org = Organization(name=name)
    db.add(org)
    await db.flush()
    return org


async def _create_studio_project(db, org_id: str, title: str = "스타일 Studio") -> BidProject:
    project = BidProject(
        org_id=org_id, created_by="testuser", title=title,
        status="draft", project_type="studio", studio_stage="style",
    )
    db.add(project)
    await db.flush()
    return project


async def _setup_user(db, org_id: str, project_id: str, username: str = "testuser"):
    db.add(Membership(org_id=org_id, user_id=username, role="editor", is_active=True))
    db.add(ProjectAccess(project_id=project_id, user_id=username, access_level="owner"))
    await db.flush()


# ---- Tests ----

@pytest.mark.asyncio
async def test_create_style_skill(db_session):
    """POST style-skills creates a project-scoped style skill."""
    from services.web_app.api.studio import create_style_skill, CreateStyleSkillRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    resp = await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(
            name="과거 제안서 기반 v1",
            
            style_json={"tone": "formal", "voice": "third_person"},
            profile_md_content="# 문체 프로필\n- 경어체 사용",
        ),
        user=user, db=db_session,
    )

    assert resp.id is not None
    assert resp.name == "과거 제안서 기반 v1"
    assert resp.version == 1
    assert resp.source_type == "uploaded"
    assert resp.project_id == project.id
    assert resp.is_shared_default is False


@pytest.mark.asyncio
async def test_pin_style_skill(db_session):
    """POST pin updates bid_projects.pinned_style_skill_id."""
    from services.web_app.api.studio import create_style_skill, pin_style_skill, CreateStyleSkillRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    skill = await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(
            name="핀 대상 스타일", 
            style_json={"tone": "casual"},
        ),
        user=user, db=db_session,
    )

    result = await pin_style_skill(
        project_id=project.id, skill_id=skill.id, user=user, db=db_session,
    )

    assert result["pinned_style_skill_id"] == skill.id

    # Verify project updated
    proj = (await db_session.execute(
        select(BidProject).where(BidProject.id == project.id)
    )).scalar_one()
    assert proj.pinned_style_skill_id == skill.id


@pytest.mark.asyncio
async def test_list_style_skills(db_session):
    """GET style-skills returns project-scoped skills."""
    from services.web_app.api.studio import create_style_skill, list_style_skills, CreateStyleSkillRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(name="스타일 A"),
        user=user, db=db_session,
    )
    await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(name="스타일 B"),
        user=user, db=db_session,
    )

    skills = await list_style_skills(project_id=project.id, user=user, db=db_session)
    assert len(skills) == 2


@pytest.mark.asyncio
async def test_derive_style_skill(db_session):
    """Derive creates v2 referencing v1."""
    from services.web_app.api.studio import create_style_skill, derive_style_skill, CreateStyleSkillRequest, DeriveStyleSkillRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    v1 = await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(
            name="원본 스타일", 
            style_json={"tone": "formal"},
        ),
        user=user, db=db_session,
    )

    v2 = await derive_style_skill(
        project_id=project.id,
        skill_id=v1.id,
        req=DeriveStyleSkillRequest(
            name="수정 스타일 v2",
            style_json={"tone": "formal", "additions": ["표 사용 강화"]},
            profile_md_content="# 수정된 문체 프로필",
        ),
        user=user, db=db_session,
    )

    assert v2.version == 2
    assert v2.derived_from_id == v1.id
    assert v2.source_type == "derived"
    assert v2.name == "수정 스타일 v2"


@pytest.mark.asyncio
async def test_promote_creates_shared_default(db_session):
    """Promote copies skill to org-level shared default."""
    from services.web_app.api.studio import create_style_skill, promote_style_skill, CreateStyleSkillRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    skill = await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(
            name="승격 대상 스타일", 
            style_json={"tone": "formal"},
            profile_md_content="# 조직 기본 문체",
        ),
        user=user, db=db_session,
    )

    result = await promote_style_skill(
        project_id=project.id, skill_id=skill.id, user=user, db=db_session,
    )

    assert result["promoted"] is True
    shared_id = result["shared_skill_id"]

    # Verify shared skill created
    shared = (await db_session.execute(
        select(ProjectStyleSkill).where(ProjectStyleSkill.id == shared_id)
    )).scalar_one()
    assert shared.project_id is None
    assert shared.is_shared_default is True
    assert shared.org_id == org.id
    assert shared.source_type == "promoted"
    assert shared.derived_from_id == skill.id
    assert shared.profile_md_content == "# 조직 기본 문체"


@pytest.mark.asyncio
async def test_promote_replaces_existing_shared_default(db_session):
    """Second promote replaces the previous shared default."""
    from services.web_app.api.studio import create_style_skill, promote_style_skill, CreateStyleSkillRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # Create and promote first skill
    s1 = await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(name="v1 스타일", style_json={"v": 1}),
        user=user, db=db_session,
    )
    r1 = await promote_style_skill(project_id=project.id, skill_id=s1.id, user=user, db=db_session)
    first_shared_id = r1["shared_skill_id"]

    # Create and promote second skill
    s2 = await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(name="v2 스타일", style_json={"v": 2}),
        user=user, db=db_session,
    )
    r2 = await promote_style_skill(project_id=project.id, skill_id=s2.id, user=user, db=db_session)
    second_shared_id = r2["shared_skill_id"]

    # Old shared default should no longer be default
    old_shared = (await db_session.execute(
        select(ProjectStyleSkill).where(ProjectStyleSkill.id == first_shared_id)
    )).scalar_one()
    assert old_shared.is_shared_default is False

    # New shared default is active
    new_shared = (await db_session.execute(
        select(ProjectStyleSkill).where(ProjectStyleSkill.id == second_shared_id)
    )).scalar_one()
    assert new_shared.is_shared_default is True


@pytest.mark.asyncio
async def test_promote_creates_audit_log(db_session):
    """Promote creates AuditLog entry."""
    from services.web_app.api.studio import create_style_skill, promote_style_skill, CreateStyleSkillRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    skill = await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(name="감사 테스트"),
        user=user, db=db_session,
    )
    await promote_style_skill(project_id=project.id, skill_id=skill.id, user=user, db=db_session)

    logs = (await db_session.execute(
        select(AuditLog).where(
            AuditLog.project_id == project.id,
            AuditLog.action == "style_skill_promoted",
        )
    )).scalars().all()
    assert len(logs) >= 1


@pytest.mark.asyncio
async def test_non_studio_project_rejected(db_session):
    """Style skill endpoints reject non-studio projects."""
    from services.web_app.api.studio import create_style_skill, CreateStyleSkillRequest
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    chat_project = BidProject(
        org_id=org.id, created_by="testuser", title="Chat",
        status="draft", project_type="chat",
    )
    db_session.add(chat_project)
    await db_session.flush()
    await _setup_user(db_session, org.id, chat_project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await create_style_skill(
            project_id=chat_project.id,
            req=CreateStyleSkillRequest(name="test"),
            user=user, db=db_session,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_no_access_user_rejected(db_session):
    """User without project access gets 404."""
    from services.web_app.api.studio import list_style_skills
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    db_session.add(Membership(org_id=org.id, user_id="outsider", role="editor", is_active=True))
    await db_session.flush()

    outsider = CurrentUser(username="outsider", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await list_style_skills(project_id=project.id, user=outsider, db=db_session)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_unpin_style_skill(db_session):
    """Unpin clears pinned_style_skill_id."""
    from services.web_app.api.studio import create_style_skill, pin_style_skill, unpin_style_skill, CreateStyleSkillRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    skill = await create_style_skill(
        project_id=project.id,
        req=CreateStyleSkillRequest(name="핀 해제 대상"),
        user=user, db=db_session,
    )
    await pin_style_skill(project_id=project.id, skill_id=skill.id, user=user, db=db_session)

    result = await unpin_style_skill(project_id=project.id, user=user, db=db_session)
    assert result["pinned_style_skill_id"] is None

    proj = (await db_session.execute(
        select(BidProject).where(BidProject.id == project.id)
    )).scalar_one()
    assert proj.pinned_style_skill_id is None
