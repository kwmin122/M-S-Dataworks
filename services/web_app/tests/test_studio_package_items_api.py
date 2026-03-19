"""Package item lifecycle + evidence upload tests.

Tests:
1. status transition: missing → uploaded (with evidence)
2. status transition: missing → waived
3. status transition: generated → verified
4. invalid transition rejected (e.g., missing → verified)
5. evidence upload creates DocumentAsset + links asset_id
6. completeness summary from API
7. non-studio project rejected
"""
from __future__ import annotations

import pytest
from unittest.mock import patch
from sqlalchemy import select

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess
from services.web_app.db.models.studio import ProjectPackageItem
from services.web_app.db.models.document import DocumentAsset
from services.web_app.db.models.base import new_cuid


# --- Helpers ---

async def _create_org(db, name: str = "패키지 테스트기관") -> Organization:
    org = Organization(name=name)
    db.add(org)
    await db.flush()
    return org


async def _create_studio_project(db, org_id: str) -> BidProject:
    project = BidProject(
        org_id=org_id, created_by="testuser", title="패키지 Studio",
        status="draft", project_type="studio", studio_stage="review",
    )
    db.add(project)
    await db.flush()
    return project


async def _setup_user(db, org_id: str, project_id: str):
    db.add(Membership(org_id=org_id, user_id="testuser", role="editor", is_active=True))
    db.add(ProjectAccess(project_id=project_id, user_id="testuser", access_level="owner"))
    await db.flush()


async def _create_package_items(db, org_id: str, project_id: str) -> list[ProjectPackageItem]:
    items = [
        ProjectPackageItem(
            project_id=project_id, org_id=org_id,
            package_category="generated_document", document_code="proposal",
            document_label="기술 제안서", required=True,
            status="generated", generation_target="proposal", sort_order=1,
        ),
        ProjectPackageItem(
            project_id=project_id, org_id=org_id,
            package_category="evidence", document_code="experience_cert",
            document_label="용역수행실적확인서", required=True,
            status="missing", sort_order=10,
        ),
        ProjectPackageItem(
            project_id=project_id, org_id=org_id,
            package_category="administrative", document_code="bid_letter",
            document_label="입찰서", required=True,
            status="missing", sort_order=20,
        ),
        ProjectPackageItem(
            project_id=project_id, org_id=org_id,
            package_category="price", document_code="price_proposal",
            document_label="가격제안서", required=False,
            status="missing", sort_order=30,
        ),
    ]
    db.add_all(items)
    await db.flush()
    return items


# ---- Tests ----

@pytest.mark.asyncio
async def test_transition_missing_to_uploaded(db_session):
    """PATCH status: missing → uploaded with evidence asset."""
    from services.web_app.api.studio import update_package_item_status, UpdatePackageItemStatusRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    items = await _create_package_items(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")
    evidence_item = items[1]  # experience_cert, status=missing

    result = await update_package_item_status(
        project_id=project.id, item_id=evidence_item.id,
        req=UpdatePackageItemStatusRequest(status="uploaded"),
        user=user, db=db_session,
    )

    assert result["status"] == "uploaded"


@pytest.mark.asyncio
async def test_transition_missing_to_waived(db_session):
    """PATCH status: missing → waived."""
    from services.web_app.api.studio import update_package_item_status, UpdatePackageItemStatusRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    items = await _create_package_items(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    result = await update_package_item_status(
        project_id=project.id, item_id=items[3].id,  # price_proposal
        req=UpdatePackageItemStatusRequest(status="waived"),
        user=user, db=db_session,
    )
    assert result["status"] == "waived"


@pytest.mark.asyncio
async def test_transition_generated_to_verified(db_session):
    """PATCH status: generated → verified."""
    from services.web_app.api.studio import update_package_item_status, UpdatePackageItemStatusRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    items = await _create_package_items(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    result = await update_package_item_status(
        project_id=project.id, item_id=items[0].id,  # proposal, status=generated
        req=UpdatePackageItemStatusRequest(status="verified"),
        user=user, db=db_session,
    )
    assert result["status"] == "verified"


@pytest.mark.asyncio
async def test_invalid_transition_rejected(db_session):
    """PATCH status: missing → verified is not allowed."""
    from services.web_app.api.studio import update_package_item_status, UpdatePackageItemStatusRequest
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    items = await _create_package_items(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await update_package_item_status(
            project_id=project.id, item_id=items[1].id,  # missing
            req=UpdatePackageItemStatusRequest(status="verified"),
            user=user, db=db_session,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_evidence_upload_creates_asset(db_session):
    """Evidence upload creates DocumentAsset and links to package item."""
    from services.web_app.api.studio import attach_evidence, AttachEvidenceRequest
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    items = await _create_package_items(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    result = await attach_evidence(
        project_id=project.id, item_id=items[1].id,
        req=AttachEvidenceRequest(
            original_filename="실적확인서.pdf",
            storage_uri="local://uploads/실적확인서.pdf",
            mime_type="application/pdf",
            size_bytes=102400,
        ),
        user=user, db=db_session,
    )

    assert result["asset_id"] is not None
    assert result["status"] == "uploaded"

    # Verify DocumentAsset created
    asset = (await db_session.execute(
        select(DocumentAsset).where(DocumentAsset.id == result["asset_id"])
    )).scalar_one()
    assert asset.original_filename == "실적확인서.pdf"
    assert asset.revision_id is None  # evidence, not a generated revision

    # Verify package item linked
    item = (await db_session.execute(
        select(ProjectPackageItem).where(ProjectPackageItem.id == items[1].id)
    )).scalar_one()
    assert item.asset_id == result["asset_id"]
    assert item.status == "uploaded"


@pytest.mark.asyncio
async def test_completeness_summary(db_session):
    """GET completeness returns total/completed/required_remaining/pct."""
    from services.web_app.api.studio import get_package_completeness
    from services.web_app.api.deps import CurrentUser

    org = await _create_org(db_session)
    project = await _create_studio_project(db_session, org.id)
    await _setup_user(db_session, org.id, project.id)
    await _create_package_items(db_session, org.id, project.id)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    summary = await get_package_completeness(
        project_id=project.id, user=user, db=db_session,
    )

    assert summary["total"] == 4
    assert summary["completed"] == 1  # proposal is generated
    assert summary["required_remaining"] == 2  # experience_cert + bid_letter still missing
    assert 0 < summary["completeness_pct"] < 100


@pytest.mark.asyncio
async def test_non_studio_project_rejected(db_session):
    """Package item status update rejected on non-studio project."""
    from services.web_app.api.studio import update_package_item_status, UpdatePackageItemStatusRequest
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

    item = ProjectPackageItem(
        project_id=chat.id, org_id=org.id,
        package_category="evidence", document_code="test",
        document_label="테스트", status="missing", sort_order=0,
    )
    db_session.add(item)
    await db_session.commit()

    user = CurrentUser(username="testuser", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await update_package_item_status(
            project_id=chat.id, item_id=item.id,
            req=UpdatePackageItemStatusRequest(status="uploaded"),
            user=user, db=db_session,
        )
    assert exc_info.value.status_code == 400
