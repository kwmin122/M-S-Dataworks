"""Route-level test: classify endpoint → package items persisted in DB.

Tests the actual endpoint function with injected deps to verify:
1. classify_project_package creates ProjectPackageItem rows
2. Items are retrievable via list_package_items
3. Re-classification replaces existing items
4. Stage advances to 'package'
5. Classification without snapshot returns 400
"""
from __future__ import annotations

import pytest
from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess, AnalysisSnapshot
from services.web_app.db.models.base import new_cuid


SERVICE_NEGOTIATED_ANALYSIS = {
    "title": "2026년 XX교육청 학사행정시스템 구축 용역",
    "issuing_org": "XX교육청",
    "budget": "8억5천만원",
    "project_period": "2026-06 ~ 2027-05",
    "evaluation_criteria": [
        {"category": "기술평가", "max_score": 70, "description": "기술제안서 평가, 배점한도 70점"},
        {"category": "가격평가", "max_score": 30, "description": "가격점수"},
    ],
    "requirements": [
        {"category": "기능요건", "description": "학적관리, 성적처리, 출결관리 모듈 구축"},
        {"category": "기술요건", "description": "클라우드 네이티브 SW 개발"},
        {"category": "실적요건", "description": "유사 정보시스템 구축 용역 수행실적"},
    ],
}


async def _setup_project_with_snapshot(db, analysis_json: dict, summary_md: str | None = None):
    """Create org + membership + studio project + analysis snapshot."""
    org = Organization(name="분류 테스트")
    db.add(org)
    await db.flush()

    db.add(Membership(org_id=org.id, user_id="classifier_user", role="editor", is_active=True))
    await db.flush()

    project = BidProject(
        org_id=org.id,
        created_by="classifier_user",
        title=analysis_json.get("title", "테스트"),
        status="draft",
        project_type="studio",
        studio_stage="rfp",
    )
    db.add(project)
    await db.flush()

    db.add(ProjectAccess(
        project_id=project.id, user_id="classifier_user", access_level="owner",
    ))

    snapshot = AnalysisSnapshot(
        id=new_cuid(),
        org_id=org.id,
        project_id=project.id,
        version=1,
        analysis_json=analysis_json,
        summary_md=summary_md,
        is_active=True,
        created_by="classifier_user",
    )
    db.add(snapshot)
    await db.flush()

    project.active_analysis_snapshot_id = snapshot.id
    await db.commit()

    return org, project


@pytest.mark.asyncio
async def test_classify_creates_package_items(db_session):
    """POST /classify creates items and advances stage to 'package'."""
    from services.web_app.api.studio import classify_project_package, list_package_items
    from services.web_app.api.deps import CurrentUser

    org, project = await _setup_project_with_snapshot(db_session, SERVICE_NEGOTIATED_ANALYSIS)
    user = CurrentUser(username="classifier_user", org_id=org.id, role="editor")

    # Classify
    result = await classify_project_package(project_id=project.id, user=user, db=db_session)

    assert result.procurement_domain == "service"
    assert result.contract_method == "negotiated"
    assert len(result.package_items) > 0

    # Check generated documents exist
    codes = {i.document_code for i in result.package_items}
    assert "proposal" in codes
    assert "execution_plan" in codes

    # Verify status differentiation: generated_document → ready_to_generate, others → missing
    for item in result.package_items:
        if item.package_category == "generated_document" and item.generation_target:
            assert item.status == "ready_to_generate", (
                f"{item.document_code}: expected ready_to_generate, got {item.status}"
            )
        else:
            assert item.status == "missing", (
                f"{item.document_code}: expected missing, got {item.status}"
            )

    # Verify stage advanced
    from sqlalchemy import select
    proj_result = await db_session.execute(
        select(BidProject).where(BidProject.id == project.id)
    )
    updated = proj_result.scalar_one()
    assert updated.studio_stage == "package"

    # List items
    items = await list_package_items(project_id=project.id, user=user, db=db_session)
    assert len(items) == len(result.package_items)


@pytest.mark.asyncio
async def test_reclassify_replaces_items(db_session):
    """Re-running classify replaces existing package items."""
    from services.web_app.api.studio import classify_project_package
    from services.web_app.api.deps import CurrentUser

    org, project = await _setup_project_with_snapshot(db_session, SERVICE_NEGOTIATED_ANALYSIS)
    user = CurrentUser(username="classifier_user", org_id=org.id, role="editor")

    # First classify
    first = await classify_project_package(project_id=project.id, user=user, db=db_session)
    first_count = len(first.package_items)

    # Re-classify (should replace, not duplicate)
    second = await classify_project_package(project_id=project.id, user=user, db=db_session)
    assert len(second.package_items) == first_count  # same count, not doubled


@pytest.mark.asyncio
async def test_classify_without_snapshot_returns_400(db_session):
    """Classify without analysis snapshot returns 400."""
    from services.web_app.api.studio import classify_project_package
    from services.web_app.api.deps import CurrentUser
    from fastapi import HTTPException

    org = Organization(name="400 테스트")
    db_session.add(org)
    await db_session.flush()

    db_session.add(Membership(org_id=org.id, user_id="no_snap_user", role="editor", is_active=True))
    await db_session.flush()

    project = BidProject(
        org_id=org.id, created_by="no_snap_user", title="스냅샷 없음",
        project_type="studio", studio_stage="rfp",
    )
    db_session.add(project)
    await db_session.flush()
    db_session.add(ProjectAccess(
        project_id=project.id, user_id="no_snap_user", access_level="owner",
    ))
    await db_session.commit()

    user = CurrentUser(username="no_snap_user", org_id=org.id, role="editor")

    with pytest.raises(HTTPException) as exc_info:
        await classify_project_package(project_id=project.id, user=user, db=db_session)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_classify_goods_rfp(db_session):
    """Goods RFP classification produces goods-specific items."""
    from services.web_app.api.studio import classify_project_package
    from services.web_app.api.deps import CurrentUser

    goods_analysis = {
        "title": "2026년 사무용 PC 및 서버 장비 구매",
        "issuing_org": "YY공단",
        "budget": "5억원",
        "evaluation_criteria": [
            {"category": "규격심사", "max_score": 60, "description": "규격적합 확인"},
        ],
        "requirements": [
            {"category": "규격요건", "description": "PC 300대, 서버 5대 납품"},
            {"category": "인증요건", "description": "시험성적서 및 카탈로그 제출"},
        ],
    }

    org, project = await _setup_project_with_snapshot(db_session, goods_analysis)
    user = CurrentUser(username="classifier_user", org_id=org.id, role="editor")

    result = await classify_project_package(project_id=project.id, user=user, db=db_session)
    assert result.procurement_domain == "goods"
    codes = {i.document_code for i in result.package_items}
    assert "catalog" in codes
    assert "test_report" in codes
