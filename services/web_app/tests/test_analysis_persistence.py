"""Tests for Task 9: Analysis persistence wiring (AnalysisSnapshot creation)."""
from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, AnalysisSnapshot


@pytest.mark.asyncio
async def test_analysis_persistence_creates_snapshot(db_session):
    """Verify that SessionAdapter.save_analysis creates AnalysisSnapshot."""
    from services.web_app.api.adapter import SessionAdapter
    from services.web_app.api.analysis_serializer import serialize_analysis_for_db
    from rfx_analyzer import RFxAnalysisResult

    # Setup: org + project
    org = Organization(name="테스트회사")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="user1", role="owner", is_active=True)
    db_session.add(member)

    project = BidProject(
        org_id=org.id,
        created_by="user1",
        title="테스트 사업",
        status="collecting_inputs",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.commit()

    # Create mock analysis result
    from rfx_analyzer import RFxRequirement

    analysis = RFxAnalysisResult(
        title="테스트 RFP",
        issuing_org="발주기관",
        budget="1억원",
        project_period="6개월",
        requirements=[
            RFxRequirement(
                category="실적요건",
                description="소프트웨어 개발 실적 3건 이상",
                is_mandatory=True,
            )
        ],
        evaluation_criteria=[],
    )

    # Act: Save analysis
    adapter = SessionAdapter(db_session)
    await adapter.save_analysis(
        project_id=project.id,
        org_id=org.id,
        analysis_json=serialize_analysis_for_db(analysis),
        summary_md="## 사업 개요\n테스트 사업입니다.",
        go_nogo_json=None,
        username="user1",
    )
    await db_session.commit()

    # Assert 1: AnalysisSnapshot created
    result = await db_session.execute(
        select(AnalysisSnapshot).where(AnalysisSnapshot.project_id == project.id)
    )
    snapshots = result.scalars().all()
    assert len(snapshots) == 1, "Should create exactly one AnalysisSnapshot"

    snapshot = snapshots[0]
    assert snapshot.org_id == org.id
    assert snapshot.project_id == project.id
    assert snapshot.version == 1
    assert snapshot.is_active is True
    assert snapshot.analysis_json["title"] == "테스트 RFP"
    assert "requirements" in snapshot.analysis_json
    assert snapshot.summary_md == "## 사업 개요\n테스트 사업입니다."

    # Assert 2: Project active pointer updated
    await db_session.refresh(project)
    assert project.active_analysis_snapshot_id == snapshot.id, \
        "Project should have active_analysis_snapshot_id set"

    # Assert 3: Project status updated
    assert project.status == "ready_for_generation", \
        "Project status should transition to 'ready_for_generation'"


@pytest.mark.asyncio
async def test_analysis_persistence_increments_version(db_session):
    """Verify that multiple analyses increment version and update is_active."""
    from services.web_app.api.adapter import SessionAdapter
    from services.web_app.api.analysis_serializer import serialize_analysis_for_db
    from rfx_analyzer import RFxAnalysisResult

    # Setup: org + project
    org = Organization(name="테스트회사")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="user1", role="owner", is_active=True)
    db_session.add(member)

    project = BidProject(
        org_id=org.id,
        created_by="user1",
        title="테스트 사업",
        status="collecting_inputs",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.commit()

    adapter = SessionAdapter(db_session)

    # Create first analysis
    analysis1 = RFxAnalysisResult(
        title="RFP v1",
        issuing_org="발주기관",
        budget="1억원",
        project_period="6개월",
        requirements=[],
        evaluation_criteria=[],
    )
    await adapter.save_analysis(
        project_id=project.id,
        org_id=org.id,
        analysis_json=serialize_analysis_for_db(analysis1),
        summary_md="v1",
        go_nogo_json=None,
        username="user1",
    )
    await db_session.commit()

    # Create second analysis
    analysis2 = RFxAnalysisResult(
        title="RFP v2",
        issuing_org="발주기관",
        budget="2억원",
        project_period="12개월",
        requirements=[],
        evaluation_criteria=[],
    )
    await adapter.save_analysis(
        project_id=project.id,
        org_id=org.id,
        analysis_json=serialize_analysis_for_db(analysis2),
        summary_md="v2",
        go_nogo_json=None,
        username="user1",
    )
    await db_session.commit()

    # Assert: Two snapshots exist
    result = await db_session.execute(
        select(AnalysisSnapshot)
        .where(AnalysisSnapshot.project_id == project.id)
        .order_by(AnalysisSnapshot.version)
    )
    snapshots = result.scalars().all()
    assert len(snapshots) == 2, "Should have 2 snapshots"

    # Assert: Version increments
    assert snapshots[0].version == 1
    assert snapshots[1].version == 2

    # Assert: Only latest is active
    assert snapshots[0].is_active is False, "Old snapshot should be inactive"
    assert snapshots[1].is_active is True, "Latest snapshot should be active"

    # Assert: Project points to latest
    await db_session.refresh(project)
    assert project.active_analysis_snapshot_id == snapshots[1].id


@pytest.mark.asyncio
async def test_analysis_persistence_with_go_nogo(db_session):
    """Verify that go_nogo_result_json is correctly stored."""
    from services.web_app.api.adapter import SessionAdapter
    from services.web_app.api.analysis_serializer import serialize_analysis_for_db
    from rfx_analyzer import RFxAnalysisResult

    # Setup
    org = Organization(name="테스트회사")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="user1", role="owner", is_active=True)
    db_session.add(member)

    project = BidProject(
        org_id=org.id,
        created_by="user1",
        title="테스트 사업",
        status="collecting_inputs",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.commit()

    # Create analysis
    analysis = RFxAnalysisResult(
        title="테스트 RFP",
        issuing_org="발주기관",
        budget="1억원",
        project_period="6개월",
        requirements=[],
        evaluation_criteria=[],
    )

    go_nogo_data = {
        "overall_decision": "GO",
        "confidence": 0.85,
        "matched_count": 5,
        "total_count": 6,
    }

    # Act
    adapter = SessionAdapter(db_session)
    await adapter.save_analysis(
        project_id=project.id,
        org_id=org.id,
        analysis_json=serialize_analysis_for_db(analysis),
        summary_md="## 요약",
        go_nogo_json=go_nogo_data,
        username="user1",
    )
    await db_session.commit()

    # Assert: go_nogo_result_json stored
    result = await db_session.execute(
        select(AnalysisSnapshot).where(AnalysisSnapshot.project_id == project.id)
    )
    snapshot = result.scalar_one()
    assert snapshot.go_nogo_result_json is not None
    assert snapshot.go_nogo_result_json["overall_decision"] == "GO"
    assert snapshot.go_nogo_result_json["confidence"] == 0.85
