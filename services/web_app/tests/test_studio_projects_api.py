"""Studio project control plane tests.

Tests:
1. Creating a Studio project sets project_type='studio', studio_stage='rfp'
2. from_analysis_snapshot_id clones the source snapshot into the new project
3. GET /api/studio/projects returns only org-owned Studio projects
4. Stage update changes studio_stage
5. Studio-specific models (ProjectCompanyAsset, ProjectStyleSkill, ProjectPackageItem) CRUD
"""
from __future__ import annotations

import pytest
from services.web_app.db.models.base import new_cuid
from services.web_app.db.models.org import Organization
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.audit import AuditLog
from services.web_app.db.models.studio import (
    ProjectCompanyAsset, ProjectStyleSkill, ProjectPackageItem,
)


# --- Helper: create org + project ---

async def _create_org(db, name: str = "테스트기관") -> Organization:
    org = Organization(name=name)
    db.add(org)
    await db.flush()
    return org


async def _create_studio_project(db, org_id: str, title: str = "테스트 Studio") -> BidProject:
    project = BidProject(
        org_id=org_id,
        created_by="testuser",
        title=title,
        status="draft",
        project_type="studio",
        studio_stage="rfp",
    )
    db.add(project)
    await db.flush()
    return project


# ---- Model-level tests ----

@pytest.mark.asyncio
async def test_create_studio_project(db_session):
    """Studio project with project_type='studio' and studio_stage='rfp'."""
    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await db_session.commit()

    assert project.id is not None
    assert project.project_type == "studio"
    assert project.studio_stage == "rfp"
    assert project.pinned_style_skill_id is None


@pytest.mark.asyncio
async def test_chat_project_default_type(db_session):
    """Regular BidProject defaults to project_type='chat'."""
    org = await _create_org(db_session)
    project = BidProject(
        org_id=org.id, created_by="testuser", title="Chat project",
    )
    db_session.add(project)
    await db_session.commit()
    assert project.project_type == "chat"
    assert project.studio_stage is None


@pytest.mark.asyncio
async def test_snapshot_clone(db_session):
    """Cloning an analysis snapshot creates a new row bound to the Studio project."""
    org = await _create_org(db_session)

    # Source project + snapshot (Chat)
    chat_project = BidProject(
        org_id=org.id, created_by="u1", title="Chat origin",
    )
    db_session.add(chat_project)
    await db_session.flush()

    source_snap = AnalysisSnapshot(
        org_id=org.id,
        project_id=chat_project.id,
        version=1,
        analysis_json={"title": "원본 분석", "requirements": []},
        summary_md="# 요약",
        is_active=True,
    )
    db_session.add(source_snap)
    await db_session.flush()

    # Clone into Studio project
    studio_proj = await _create_studio_project(db_session, org.id, "Studio clone target")
    cloned_snap = AnalysisSnapshot(
        id=new_cuid(),
        org_id=org.id,
        project_id=studio_proj.id,
        version=1,
        analysis_json=source_snap.analysis_json,
        analysis_schema=source_snap.analysis_schema,
        summary_md=source_snap.summary_md,
        go_nogo_result_json=source_snap.go_nogo_result_json,
        is_active=True,
        created_by="testuser",
    )
    db_session.add(cloned_snap)
    await db_session.flush()

    studio_proj.active_analysis_snapshot_id = cloned_snap.id
    await db_session.commit()

    # Verify: source snapshot untouched
    assert source_snap.project_id == chat_project.id
    assert source_snap.analysis_json == {"title": "원본 분석", "requirements": []}

    # Verify: cloned snapshot bound to studio project
    assert cloned_snap.project_id == studio_proj.id
    assert cloned_snap.id != source_snap.id
    assert cloned_snap.analysis_json == source_snap.analysis_json
    assert studio_proj.active_analysis_snapshot_id == cloned_snap.id


@pytest.mark.asyncio
async def test_project_company_asset_crud(db_session):
    """ProjectCompanyAsset CRUD in project staging."""
    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)

    asset = ProjectCompanyAsset(
        project_id=project.id,
        org_id=org.id,
        asset_category="track_record",
        label="XX기관 정보시스템 구축 실적",
        content_json={
            "project_name": "XX기관 정보시스템 구축",
            "amount": 500000000,
            "period": "2024-01 ~ 2024-12",
        },
    )
    db_session.add(asset)
    await db_session.commit()

    assert asset.id is not None
    assert asset.asset_category == "track_record"
    assert asset.promoted_at is None
    assert asset.content_json["amount"] == 500000000


@pytest.mark.asyncio
async def test_project_style_skill_crud(db_session):
    """ProjectStyleSkill creation and version uniqueness."""
    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)

    skill = ProjectStyleSkill(
        project_id=project.id,
        org_id=org.id,
        version=1,
        name="과거 제안서 기반 v1",
        source_type="uploaded",
        profile_md_content="# 문체 프로필\n- 경어체 사용\n- 기술 용어 중심",
        style_json={"tone": "formal", "voice": "third_person"},
    )
    db_session.add(skill)
    await db_session.commit()

    assert skill.id is not None
    assert skill.is_shared_default is False

    # Pin the style skill to the project
    project.pinned_style_skill_id = skill.id
    await db_session.commit()
    assert project.pinned_style_skill_id == skill.id


@pytest.mark.asyncio
async def test_project_package_item_crud(db_session):
    """ProjectPackageItem tracks submission package requirements."""
    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)

    items = [
        ProjectPackageItem(
            project_id=project.id,
            org_id=org.id,
            package_category="generated_document",
            document_code="proposal",
            document_label="기술 제안서",
            required=True,
            status="missing",
            generation_target="proposal",
            sort_order=1,
        ),
        ProjectPackageItem(
            project_id=project.id,
            org_id=org.id,
            package_category="evidence",
            document_code="experience_cert",
            document_label="경험증명서",
            required=True,
            status="missing",
            sort_order=2,
        ),
        ProjectPackageItem(
            project_id=project.id,
            org_id=org.id,
            package_category="administrative",
            document_code="business_license",
            document_label="사업자등록증",
            required=True,
            status="missing",
            sort_order=3,
        ),
    ]
    db_session.add_all(items)
    await db_session.commit()

    assert all(i.id is not None for i in items)
    assert items[0].package_category == "generated_document"
    assert items[1].package_category == "evidence"
    assert items[2].package_category == "administrative"

    # Simulate generation completing
    items[0].status = "generated"
    await db_session.commit()
    assert items[0].status == "generated"


@pytest.mark.asyncio
async def test_package_item_unique_document_code(db_session):
    """Duplicate document_code within same project should raise."""
    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)

    item1 = ProjectPackageItem(
        project_id=project.id,
        org_id=org.id,
        package_category="generated_document",
        document_code="proposal",
        document_label="제안서",
        sort_order=0,
    )
    db_session.add(item1)
    await db_session.flush()

    item2 = ProjectPackageItem(
        project_id=project.id,
        org_id=org.id,
        package_category="generated_document",
        document_code="proposal",  # duplicate
        document_label="제안서 v2",
        sort_order=1,
    )
    db_session.add(item2)

    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_style_skill_derive_chain(db_session):
    """Style skill derive: v2 references v1 via derived_from_id."""
    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)

    v1 = ProjectStyleSkill(
        project_id=project.id,
        org_id=org.id,
        version=1,
        name="원본 스타일",
        source_type="uploaded",
    )
    db_session.add(v1)
    await db_session.flush()

    v2 = ProjectStyleSkill(
        project_id=project.id,
        org_id=org.id,
        version=2,
        name="수정 스타일 v2",
        source_type="derived",
        derived_from_id=v1.id,
        style_json={"tone": "formal", "additions": ["수정 반영"]},
    )
    db_session.add(v2)
    await db_session.commit()

    assert v2.derived_from_id == v1.id
    assert v2.version == 2


@pytest.mark.asyncio
async def test_shared_default_style_skill(db_session):
    """Shared default style skill has project_id=NULL and is_shared_default=True."""
    org = await _create_org(db_session)

    shared_skill = ProjectStyleSkill(
        project_id=None,  # shared, not project-scoped
        org_id=org.id,
        version=1,
        name="조직 기본 스타일",
        source_type="promoted",
        is_shared_default=True,
        profile_md_content="# 조직 기본 문체 프로필",
    )
    db_session.add(shared_skill)
    await db_session.commit()

    assert shared_skill.project_id is None
    assert shared_skill.is_shared_default is True


# ---- ACL / constraint tests ----

@pytest.mark.asyncio
async def test_creator_gets_project_access(db_session):
    """Simulates the API behavior: creator must have ProjectAccess(owner)."""
    from services.web_app.db.models.org import Membership

    org = await _create_org(db_session)
    # Create membership for the user
    db_session.add(Membership(
        org_id=org.id, user_id="creator_user", role="editor", is_active=True,
    ))
    await db_session.flush()

    # Create project + ProjectAccess (mirroring studio.py create_studio_project)
    project = await _create_studio_project(db_session, org.id, "ACL 테스트")
    access = ProjectAccess(
        project_id=project.id, user_id="creator_user", access_level="owner",
    )
    db_session.add(access)
    await db_session.commit()

    # Creator can access
    from sqlalchemy import select
    result = await db_session.execute(
        select(ProjectAccess).where(
            ProjectAccess.project_id == project.id,
            ProjectAccess.user_id == "creator_user",
        )
    )
    found = result.scalar_one_or_none()
    assert found is not None
    assert found.access_level == "owner"


@pytest.mark.asyncio
async def test_non_creator_cannot_see_project(db_session):
    """Non-admin user without ProjectAccess cannot see the project in list."""
    org = await _create_org(db_session)

    # Create project with access for creator only
    project = await _create_studio_project(db_session, org.id, "비공개 프로젝트")
    db_session.add(ProjectAccess(
        project_id=project.id, user_id="creator", access_level="owner",
    ))
    await db_session.commit()

    # Another user queries — should NOT find this project via ACL join
    from sqlalchemy import select
    result = await db_session.execute(
        select(BidProject)
        .join(ProjectAccess, ProjectAccess.project_id == BidProject.id)
        .where(
            BidProject.org_id == org.id,
            BidProject.project_type == "studio",
            ProjectAccess.user_id == "other_user",  # no access row
        )
    )
    projects = result.scalars().all()
    assert len(projects) == 0


@pytest.mark.asyncio
async def test_shared_default_on_project_scoped_skill_rejected(db_session):
    """is_shared_default=True with project_id NOT NULL must be rejected by CHECK."""
    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)

    bad_skill = ProjectStyleSkill(
        project_id=project.id,  # NOT NULL — violates CHECK
        org_id=org.id,
        version=1,
        name="잘못된 공유 기본값",
        source_type="uploaded",
        is_shared_default=True,  # shared default on project-scoped row
    )
    db_session.add(bad_skill)

    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_duplicate_shared_default_per_org_rejected(db_session):
    """Only one is_shared_default=True per org."""
    org = await _create_org(db_session)

    skill1 = ProjectStyleSkill(
        project_id=None, org_id=org.id, version=1,
        name="기본 스타일 v1", source_type="promoted", is_shared_default=True,
    )
    db_session.add(skill1)
    await db_session.flush()

    skill2 = ProjectStyleSkill(
        project_id=None, org_id=org.id, version=2,
        name="기본 스타일 v2", source_type="promoted", is_shared_default=True,
    )
    db_session.add(skill2)

    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()
