"""Model CRUD + constraint tests. Requires PostgreSQL (BID_TEST_DATABASE_URL)."""
from __future__ import annotations

import pytest
from services.web_app.db.models.base import new_cuid
from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess, SourceDocument, AnalysisSnapshot
from services.web_app.db.models.document import DocumentRun, DocumentRevision, DocumentAsset, ProjectCurrentDocument
from services.web_app.db.models.company import CompanyProfile, CompanyTrackRecord, CompanyPersonnel
from services.web_app.db.models.audit import AuditLog


def test_cuid_generates_unique_ids():
    ids = {new_cuid() for _ in range(50)}
    assert len(ids) == 50


@pytest.mark.asyncio
async def test_create_organization(db_session):
    org = Organization(name="MS솔루션")
    db_session.add(org)
    await db_session.commit()
    assert org.id is not None
    assert org.name == "MS솔루션"


@pytest.mark.asyncio
async def test_create_membership(db_session):
    org = Organization(name="테스트기관")
    db_session.add(org)
    await db_session.flush()

    member = Membership(
        org_id=org.id,
        user_id="testuser",
        role="owner",
        is_active=True,
    )
    db_session.add(member)
    await db_session.commit()
    assert member.id is not None
    assert member.role == "owner"


@pytest.mark.asyncio
async def test_create_bid_project(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(
        org_id=org.id,
        created_by="testuser",
        title="XX기관 정보시스템 구축",
        status="draft",
    )
    db_session.add(project)
    await db_session.commit()
    assert project.id is not None
    assert project.status == "draft"


@pytest.mark.asyncio
async def test_create_analysis_snapshot(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트 사업")
    db_session.add(project)
    await db_session.flush()

    snapshot = AnalysisSnapshot(
        org_id=org.id,
        project_id=project.id,
        version=1,
        analysis_json={"title": "테스트"},
        is_active=True,
    )
    db_session.add(snapshot)
    await db_session.commit()
    assert snapshot.id is not None
    assert snapshot.version == 1


@pytest.mark.asyncio
async def test_create_document_asset(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(project)
    await db_session.flush()

    asset = DocumentAsset(
        org_id=org.id,
        project_id=project.id,
        asset_type="original",
        storage_uri="s3://kira-assets/test/file.pdf",
        upload_status="presigned_issued",
        original_filename="공고문.pdf",
        mime_type="application/pdf",
    )
    db_session.add(asset)
    await db_session.commit()
    assert asset.id is not None


@pytest.mark.asyncio
async def test_create_company_profile(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    profile = CompanyProfile(
        org_id=org.id,
        company_name="MS솔루션",
        licenses={"specialties": ["SI", "SW개발"]},
    )
    db_session.add(profile)
    await db_session.commit()
    assert profile.id is not None
    assert profile.company_name == "MS솔루션"


@pytest.mark.asyncio
async def test_create_audit_log(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    audit = AuditLog(
        org_id=org.id,
        user_id="testuser",
        action="test_action",
        target_type="test",
        target_id="test_id",
    )
    db_session.add(audit)
    await db_session.commit()
    assert audit.id is not None
