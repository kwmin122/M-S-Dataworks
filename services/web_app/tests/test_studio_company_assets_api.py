"""Company asset staging + promote tests for Studio projects.

Tests:
1. staging write does NOT pollute shared CompanyDB
2. merged view shows shared + staging combined
3. promote writes to shared CompanyProfile/CompanyTrackRecord/CompanyPersonnel
4. promote sets promoted_at + promoted_to_id
5. promote creates AuditLog
6. non-access user is rejected (404)
7. technology/certification/raw_document staging stored but NOT promotable
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from services.web_app.db.models.base import new_cuid
from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess
from services.web_app.db.models.audit import AuditLog
from services.web_app.db.models.studio import ProjectCompanyAsset
from services.web_app.db.models.company import (
    CompanyProfile, CompanyTrackRecord, CompanyPersonnel,
)


# --- Helpers ---

async def _create_org(db, name: str = "회사자산 테스트기관") -> Organization:
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
        studio_stage="company",
    )
    db.add(project)
    await db.flush()
    return project


async def _create_user_with_access(db, org_id: str, project_id: str, username: str = "testuser", role: str = "editor"):
    """Create membership + project access."""
    db.add(Membership(org_id=org_id, user_id=username, role=role, is_active=True))
    db.add(ProjectAccess(project_id=project_id, user_id=username, access_level="owner"))
    await db.flush()


async def _seed_shared_track_record(db, org_id: str) -> CompanyTrackRecord:
    """Seed a shared track record (already in shared CompanyDB)."""
    record = CompanyTrackRecord(
        org_id=org_id,
        project_name="기존 공유 실적",
        client_name="국토교통부",
        contract_amount=300_000_000,
        period_start=date(2023, 1, 1),
        period_end=date(2023, 12, 31),
        description="기존에 등록된 공유 실적",
    )
    db.add(record)
    await db.flush()
    return record


async def _seed_shared_personnel(db, org_id: str) -> CompanyPersonnel:
    person = CompanyPersonnel(
        org_id=org_id,
        name="홍길동",
        role="PM",
        years_experience=10,
        description="기존 공유 인력",
    )
    db.add(person)
    await db.flush()
    return person


async def _seed_shared_profile(db, org_id: str) -> CompanyProfile:
    profile = CompanyProfile(
        org_id=org_id,
        company_name="테스트 주식회사",
        business_type="IT서비스",
        headcount=50,
    )
    db.add(profile)
    await db.flush()
    return profile


# ---- Route-level tests (call endpoint functions with injected deps) ----

@pytest.mark.asyncio
async def test_staging_write_does_not_pollute_shared(db_session):
    """POST company-assets creates ProjectCompanyAsset; shared tables unchanged."""
    from services.web_app.api.studio import add_company_asset, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # Count shared records before
    before_count = len((await db_session.execute(
        select(CompanyTrackRecord).where(CompanyTrackRecord.org_id == org.id)
    )).scalars().all())

    # Add staging asset
    req = CompanyAssetRequest(
        asset_category="track_record",
        label="스테이징 실적",
        content_json={
            "project_name": "새 프로젝트",
            "client_name": "과학기술정보통신부",
            "contract_amount": 500_000_000,
        },
    )
    result = await add_company_asset(
        project_id=project.id, req=req, user=user, db=db_session,
    )

    # Staging asset created
    assert result.id is not None
    assert result.asset_category == "track_record"
    assert result.promoted_at is None

    # Shared table NOT polluted
    after_count = len((await db_session.execute(
        select(CompanyTrackRecord).where(CompanyTrackRecord.org_id == org.id)
    )).scalars().all())
    assert after_count == before_count


@pytest.mark.asyncio
async def test_merged_view_shows_shared_and_staging(db_session):
    """GET company-merged returns both shared records and staging assets."""
    from services.web_app.api.studio import add_company_asset, get_company_merged, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # Seed shared data
    await _seed_shared_track_record(db_session, org.id)
    await _seed_shared_personnel(db_session, org.id)
    await _seed_shared_profile(db_session, org.id)
    await db_session.commit()

    # Add staging assets
    await add_company_asset(
        project_id=project.id,
        req=CompanyAssetRequest(
            asset_category="track_record",
            label="스테이징 실적",
            content_json={"project_name": "스테이징 프로젝트"},
        ),
        user=user, db=db_session,
    )
    await add_company_asset(
        project_id=project.id,
        req=CompanyAssetRequest(
            asset_category="personnel",
            label="스테이징 인력",
            content_json={"name": "김철수", "role": "개발자"},
        ),
        user=user, db=db_session,
    )

    # Get merged view
    merged = await get_company_merged(project_id=project.id, user=user, db=db_session)

    # Should see both shared and staging
    assert merged["profile"] is not None
    assert merged["profile"]["company_name"] == "테스트 주식회사"
    assert len(merged["track_records"]) >= 2  # 1 shared + 1 staging
    assert len(merged["personnel"]) >= 2  # 1 shared + 1 staging

    # Verify staging items are tagged
    staging_records = [r for r in merged["track_records"] if r.get("source") == "staging"]
    shared_records = [r for r in merged["track_records"] if r.get("source") == "shared"]
    assert len(staging_records) >= 1
    assert len(shared_records) >= 1


@pytest.mark.asyncio
async def test_promote_writes_to_shared(db_session):
    """POST promote copies staging track_record to shared CompanyTrackRecord."""
    from services.web_app.api.studio import add_company_asset, promote_company_asset, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # Add staging asset
    req = CompanyAssetRequest(
        asset_category="track_record",
        label="승격 대상 실적",
        content_json={
            "project_name": "승격 프로젝트",
            "client_name": "행정안전부",
            "contract_amount": 200_000_000,
        },
    )
    asset_resp = await add_company_asset(
        project_id=project.id, req=req, user=user, db=db_session,
    )

    # Promote
    promote_result = await promote_company_asset(
        project_id=project.id,
        asset_id=asset_resp.id,
        user=user,
        db=db_session,
    )

    assert promote_result["promoted"] is True

    # Verify shared record created
    shared = (await db_session.execute(
        select(CompanyTrackRecord).where(
            CompanyTrackRecord.org_id == org.id,
            CompanyTrackRecord.project_name == "승격 프로젝트",
        )
    )).scalar_one_or_none()
    assert shared is not None
    assert shared.client_name == "행정안전부"
    assert shared.contract_amount == 200_000_000


@pytest.mark.asyncio
async def test_promote_sets_audit_fields(db_session):
    """After promote, promoted_at and promoted_to_id are set on the staging asset."""
    from services.web_app.api.studio import add_company_asset, promote_company_asset, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    asset_resp = await add_company_asset(
        project_id=project.id,
        req=CompanyAssetRequest(
            asset_category="personnel",
            label="승격 대상 인력",
            content_json={"name": "이영희", "role": "디자이너", "years_experience": 5},
        ),
        user=user, db=db_session,
    )

    await promote_company_asset(
        project_id=project.id, asset_id=asset_resp.id, user=user, db=db_session,
    )

    # Reload staging asset
    staging = (await db_session.execute(
        select(ProjectCompanyAsset).where(ProjectCompanyAsset.id == asset_resp.id)
    )).scalar_one()

    assert staging.promoted_at is not None
    assert staging.promoted_to_id is not None


@pytest.mark.asyncio
async def test_promote_creates_audit_log(db_session):
    """Promote creates an AuditLog entry."""
    from services.web_app.api.studio import add_company_asset, promote_company_asset, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    asset_resp = await add_company_asset(
        project_id=project.id,
        req=CompanyAssetRequest(
            asset_category="track_record",
            label="감사 로그 테스트 실적",
            content_json={"project_name": "감사 실적"},
        ),
        user=user, db=db_session,
    )

    await promote_company_asset(
        project_id=project.id, asset_id=asset_resp.id, user=user, db=db_session,
    )

    # Check AuditLog
    logs = (await db_session.execute(
        select(AuditLog).where(
            AuditLog.project_id == project.id,
            AuditLog.action == "company_asset_promoted",
        )
    )).scalars().all()
    assert len(logs) >= 1
    assert logs[0].target_type == "project_company_asset"
    assert logs[0].target_id == asset_resp.id


@pytest.mark.asyncio
async def test_no_access_user_rejected(db_session):
    """User without project access gets 404."""
    from services.web_app.api.studio import list_company_assets
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    # Only create membership, NOT project access
    db_session.add(Membership(org_id=org.id, user_id="outsider", role="editor", is_active=True))
    await db_session.flush()

    outsider = CurrentUser(username="outsider", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await list_company_assets(project_id=project.id, user=outsider, db=db_session)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_technology_staging_but_no_promote(db_session):
    """technology/certification/raw_document can be staged but NOT promoted."""
    from services.web_app.api.studio import add_company_asset, promote_company_asset, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # Staging works for technology
    asset_resp = await add_company_asset(
        project_id=project.id,
        req=CompanyAssetRequest(
            asset_category="technology",
            label="React 기술",
            content_json={"name": "React", "level": "expert"},
        ),
        user=user, db=db_session,
    )
    assert asset_resp.id is not None

    # Promote should be rejected
    with pytest.raises(HTTPException) as exc_info:
        await promote_company_asset(
            project_id=project.id, asset_id=asset_resp.id, user=user, db=db_session,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_promote_profile_to_shared(db_session):
    """Promote profile asset upserts CompanyProfile (org-level singleton)."""
    from services.web_app.api.studio import add_company_asset, promote_company_asset, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # Seed existing profile
    await _seed_shared_profile(db_session, org.id)
    await db_session.commit()

    # Stage a profile update
    asset_resp = await add_company_asset(
        project_id=project.id,
        req=CompanyAssetRequest(
            asset_category="profile",
            label="회사 기본정보 수정",
            content_json={
                "company_name": "업데이트된 주식회사",
                "business_type": "AI서비스",
                "headcount": 100,
            },
        ),
        user=user, db=db_session,
    )

    # Promote — should update existing profile
    await promote_company_asset(
        project_id=project.id, asset_id=asset_resp.id, user=user, db=db_session,
    )

    # Verify shared profile updated
    profile = (await db_session.execute(
        select(CompanyProfile).where(CompanyProfile.org_id == org.id)
    )).scalar_one()
    assert profile.company_name == "업데이트된 주식회사"
    assert profile.headcount == 100


@pytest.mark.asyncio
async def test_list_staging_assets(db_session):
    """GET company-assets returns only staging assets for this project."""
    from services.web_app.api.studio import add_company_asset, list_company_assets, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # Add 3 staging assets
    for i, cat in enumerate(["track_record", "personnel", "technology"]):
        await add_company_asset(
            project_id=project.id,
            req=CompanyAssetRequest(
                asset_category=cat,
                label=f"자산 {i}",
                content_json={"idx": i},
            ),
            user=user, db=db_session,
        )

    assets = await list_company_assets(project_id=project.id, user=user, db=db_session)
    assert len(assets) == 3


@pytest.mark.asyncio
async def test_already_promoted_asset_rejected(db_session):
    """Cannot promote an asset that was already promoted."""
    from services.web_app.api.studio import add_company_asset, promote_company_asset, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    asset_resp = await add_company_asset(
        project_id=project.id,
        req=CompanyAssetRequest(
            asset_category="track_record",
            label="이중 승격 테스트",
            content_json={"project_name": "이중 승격"},
        ),
        user=user, db=db_session,
    )

    # First promote — success
    await promote_company_asset(
        project_id=project.id, asset_id=asset_resp.id, user=user, db=db_session,
    )

    # Second promote — should fail
    with pytest.raises(HTTPException) as exc_info:
        await promote_company_asset(
            project_id=project.id, asset_id=asset_resp.id, user=user, db=db_session,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_non_studio_project_rejected(db_session):
    """Company asset endpoints reject non-studio (chat) projects."""
    from services.web_app.api.studio import add_company_asset, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    # Create a CHAT project (not studio)
    chat_project = BidProject(
        org_id=org.id,
        created_by="testuser",
        title="Chat 프로젝트",
        status="draft",
        project_type="chat",
    )
    db_session.add(chat_project)
    await db_session.flush()
    await _create_user_with_access(db_session, org.id, chat_project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await add_company_asset(
            project_id=chat_project.id,
            req=CompanyAssetRequest(
                asset_category="track_record",
                label="chat에는 안 됨",
                content_json={"project_name": "test"},
            ),
            user=user, db=db_session,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_promote_profile_new_org_without_existing(db_session):
    """Promote profile on an org with NO existing CompanyProfile creates one."""
    from services.web_app.api.studio import add_company_asset, promote_company_asset, CompanyAssetRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session, "빈 조직")
    project = await _create_studio_project(db_session, org.id)
    await _create_user_with_access(db_session, org.id, project.id)
    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    # No shared profile exists — stage one
    asset_resp = await add_company_asset(
        project_id=project.id,
        req=CompanyAssetRequest(
            asset_category="profile",
            label="신규 회사정보",
            content_json={"company_name": "새 회사", "headcount": 10},
        ),
        user=user, db=db_session,
    )

    # Promote should CREATE a new CompanyProfile
    await promote_company_asset(
        project_id=project.id, asset_id=asset_resp.id, user=user, db=db_session,
    )

    profile = (await db_session.execute(
        select(CompanyProfile).where(CompanyProfile.org_id == org.id)
    )).scalar_one()
    assert profile.company_name == "새 회사"
    assert profile.headcount == 10
