"""Layer 2: PostgreSQL Integration Tests — JSONB, partial index, CHECK, deferrable FK."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from services.web_app.db.models.project import BidProject, AnalysisSnapshot
from services.web_app.db.models.org import Organization


@pytest.mark.asyncio
async def test_jsonb_query(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    proj = BidProject(
        org_id=org.id, created_by="u1", title="테스트",
        settings_json={"total_pages": 50, "template": "standard"},
    )
    db_session.add(proj)
    await db_session.commit()

    result = await db_session.execute(
        text("SELECT id FROM bid_projects WHERE settings_json @> :val"),
        {"val": '{"total_pages": 50}'},
    )
    row = result.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_partial_unique_index_analysis_snapshot(db_session):
    """Only one active snapshot per project (idx_analysis_active)."""
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    proj = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(proj)
    await db_session.flush()

    s1 = AnalysisSnapshot(
        org_id=org.id, project_id=proj.id, version=1,
        analysis_json={"v": 1}, is_active=True,
    )
    db_session.add(s1)
    await db_session.commit()

    s2 = AnalysisSnapshot(
        org_id=org.id, project_id=proj.id, version=2,
        analysis_json={"v": 2}, is_active=True,
    )
    db_session.add(s2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_check_constraint_rejects_invalid_status(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    proj = BidProject(
        org_id=org.id, created_by="u1", title="테스트",
        status="invalid_status",
    )
    db_session.add(proj)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_deferrable_fk_bid_project_analysis(db_session):
    """bid_projects.active_analysis_snapshot_id FK is deferrable."""
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    proj = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(proj)
    await db_session.flush()

    snapshot = AnalysisSnapshot(
        org_id=org.id, project_id=proj.id, version=1,
        analysis_json={}, is_active=True,
    )
    db_session.add(snapshot)
    await db_session.flush()

    proj.active_analysis_snapshot_id = snapshot.id
    await db_session.commit()


@pytest.mark.asyncio
async def test_legacy_session_id_unique(db_session):
    """legacy_session_id uniqueness constraint."""
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    p1 = BidProject(
        org_id=org.id, created_by="u1", title="P1",
        legacy_session_id="session_abc",
    )
    db_session.add(p1)
    await db_session.commit()

    p2 = BidProject(
        org_id=org.id, created_by="u1", title="P2",
        legacy_session_id="session_abc",
    )
    db_session.add(p2)
    with pytest.raises(Exception):
        await db_session.commit()
