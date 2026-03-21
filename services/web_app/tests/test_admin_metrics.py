"""Admin observability metrics endpoint tests. Requires PostgreSQL (BID_TEST_DATABASE_URL)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from services.web_app.db.models.org import Organization
from services.web_app.db.models.audit import AuditLog
from services.web_app.db.models.usage import UsageEvent
from services.web_app.services.usage_tracker import emit_usage_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_org(db, name: str = "메트릭테스트") -> Organization:
    org = Organization(name=name)
    db.add(org)
    await db.flush()
    return org


async def _seed_usage_events(db, org_id: str) -> None:
    """Seed a set of usage events covering various event_types, doc_types, statuses."""
    events = [
        {"event_type": "generate", "status": "success", "doc_type": "proposal", "model_name": "gpt-4o", "token_count": 2000, "duration_ms": 45000},
        {"event_type": "generate", "status": "success", "doc_type": "proposal", "model_name": "gpt-4o", "token_count": 1500, "duration_ms": 38000},
        {"event_type": "generate", "status": "failure", "doc_type": "execution_plan", "model_name": "gpt-4o-mini", "token_count": 500, "duration_ms": 5000, "error_message": "timeout"},
        {"event_type": "analyze", "status": "success", "doc_type": None, "model_name": "gpt-4o-mini", "token_count": 800, "duration_ms": 12000},
        {"event_type": "classify", "status": "success", "doc_type": None, "model_name": None, "token_count": None, "duration_ms": 200},
        {"event_type": "upload", "status": "success", "doc_type": None, "model_name": None, "token_count": None, "duration_ms": 1500},
        {"event_type": "generate", "status": "timeout", "doc_type": "proposal", "model_name": "gpt-4o", "token_count": None, "duration_ms": 120000},
    ]
    for evt in events:
        await emit_usage_event(
            db,
            org_id=org_id,
            event_type=evt["event_type"],
            status=evt["status"],
            doc_type=evt.get("doc_type"),
            model_name=evt.get("model_name"),
            token_count=evt.get("token_count"),
            duration_ms=evt.get("duration_ms"),
            error_message=evt.get("error_message"),
        )
    await db.flush()


async def _seed_audit_logs(db, org_id: str) -> None:
    """Seed audit logs for quality signals."""
    # Manual override
    db.add(AuditLog(
        org_id=org_id,
        user_id="testuser",
        action="package_manual_override",
        target_type="bid_project",
        target_id="proj-1",
        detail_json={"domain_override": {"from": "auto", "to": "SI"}},
    ))
    db.add(AuditLog(
        org_id=org_id,
        user_id="testuser",
        action="package_manual_override",
        target_type="bid_project",
        target_id="proj-2",
        detail_json={"presentation_added": True},
    ))
    # Low confidence classify
    db.add(AuditLog(
        org_id=org_id,
        user_id="testuser",
        action="package_classified",
        target_type="bid_project",
        target_id="proj-1",
        detail_json={"review_required": True, "confidence": 0.45},
    ))
    # High confidence classify (should NOT count)
    db.add(AuditLog(
        org_id=org_id,
        user_id="testuser",
        action="package_classified",
        target_type="bid_project",
        target_id="proj-2",
        detail_json={"review_required": False, "confidence": 0.92},
    ))
    await db.flush()


# ---------------------------------------------------------------------------
# Tests — model-level queries (mirror the endpoint logic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usage_summary_aggregation(db_session):
    """Verify total, success, failure, timeout counts from seeded events."""
    from sqlalchemy import func as sa_func

    org = await _make_org(db_session)
    await _seed_usage_events(db_session, org.id)

    row = (await db_session.execute(
        select(
            sa_func.count().label("total"),
            sa_func.count().filter(UsageEvent.status == "success").label("success"),
            sa_func.count().filter(UsageEvent.status == "failure").label("failure"),
            sa_func.count().filter(UsageEvent.status == "timeout").label("timeout"),
        ).where(UsageEvent.org_id == org.id)
    )).one()

    assert row.total == 7
    assert row.success == 5
    assert row.failure == 1
    assert row.timeout == 1


@pytest.mark.asyncio
async def test_by_event_type_aggregation(db_session):
    """Group-by event_type returns correct counts."""
    from sqlalchemy import func as sa_func

    org = await _make_org(db_session)
    await _seed_usage_events(db_session, org.id)

    rows = (await db_session.execute(
        select(
            UsageEvent.event_type,
            sa_func.count().label("count"),
        ).where(UsageEvent.org_id == org.id).group_by(UsageEvent.event_type)
    )).all()
    by_type = {r.event_type: r.count for r in rows}

    # 4 generate events: 2 success + 1 failure + 1 timeout
    assert by_type["generate"] == 4
    assert by_type["analyze"] == 1
    assert by_type["classify"] == 1
    assert by_type["upload"] == 1


@pytest.mark.asyncio
async def test_by_doc_type_aggregation(db_session):
    """Group-by doc_type filters NULL doc_types."""
    from sqlalchemy import func as sa_func

    org = await _make_org(db_session)
    await _seed_usage_events(db_session, org.id)

    rows = (await db_session.execute(
        select(
            UsageEvent.doc_type,
            sa_func.count().label("count"),
        ).where(
            UsageEvent.org_id == org.id,
            UsageEvent.doc_type.isnot(None),
        ).group_by(UsageEvent.doc_type)
    )).all()
    by_doc = {r.doc_type: r.count for r in rows}

    assert by_doc["proposal"] == 3
    assert by_doc["execution_plan"] == 1
    assert "analyze" not in by_doc  # doc_type was None


@pytest.mark.asyncio
async def test_cost_by_model(db_session):
    """Token and cost aggregation by model."""
    from sqlalchemy import func as sa_func

    org = await _make_org(db_session)
    await _seed_usage_events(db_session, org.id)

    rows = (await db_session.execute(
        select(
            UsageEvent.model_name,
            sa_func.coalesce(sa_func.sum(UsageEvent.token_count), 0).label("tokens"),
            sa_func.coalesce(sa_func.sum(UsageEvent.estimated_cost_usd), 0).label("cost_usd"),
        ).where(
            UsageEvent.org_id == org.id,
            UsageEvent.model_name.isnot(None),
        ).group_by(UsageEvent.model_name)
    )).all()
    by_model = {r.model_name: {"tokens": int(r.tokens), "cost_usd": float(r.cost_usd)} for r in rows}

    # gpt-4o events: 2000 + 1500 + 0(timeout) = 3500 tokens
    assert by_model["gpt-4o"]["tokens"] == 3500
    # gpt-4o-mini events: 500 + 800 = 1300 tokens
    assert by_model["gpt-4o-mini"]["tokens"] == 1300
    # Both should have non-zero cost
    assert by_model["gpt-4o"]["cost_usd"] > 0
    assert by_model["gpt-4o-mini"]["cost_usd"] > 0


@pytest.mark.asyncio
async def test_quality_signals_from_audit(db_session):
    """Override count and low-confidence count from AuditLog."""
    from sqlalchemy import func as sa_func

    org = await _make_org(db_session)
    await _seed_audit_logs(db_session, org.id)

    override_count = (await db_session.execute(
        select(sa_func.count()).where(
            AuditLog.org_id == org.id,
            AuditLog.action == "package_manual_override",
        )
    )).scalar() or 0

    low_conf_count = (await db_session.execute(
        select(sa_func.count()).where(
            AuditLog.org_id == org.id,
            AuditLog.action == "package_classified",
            AuditLog.detail_json["review_required"].as_boolean() == True,  # noqa: E712
        )
    )).scalar() or 0

    assert override_count == 2
    assert low_conf_count == 1


@pytest.mark.asyncio
async def test_daily_trend(db_session):
    """Daily trend groups events by day."""
    from sqlalchemy import func as sa_func, text as sa_text

    org = await _make_org(db_session)
    await _seed_usage_events(db_session, org.id)

    rows = (await db_session.execute(
        select(
            sa_func.date_trunc("day", UsageEvent.created_at).label("day"),
            sa_func.count().label("events"),
            sa_func.count().filter(UsageEvent.status == "success").label("success"),
            sa_func.count().filter(UsageEvent.status == "failure").label("failure"),
        ).where(
            UsageEvent.org_id == org.id,
        ).group_by(sa_text("1")).order_by(sa_text("1"))
    )).all()

    # All events are created in same test → should be 1 day
    assert len(rows) == 1
    assert rows[0].events == 7
    assert rows[0].success == 5
    assert rows[0].failure == 1


@pytest.mark.asyncio
async def test_empty_org_returns_zeros(db_session):
    """An org with no usage events should return all zeros."""
    from sqlalchemy import func as sa_func

    org = await _make_org(db_session, "빈조직")

    row = (await db_session.execute(
        select(
            sa_func.count().label("total"),
            sa_func.count().filter(UsageEvent.status == "success").label("success"),
        ).where(UsageEvent.org_id == org.id)
    )).one()

    assert row.total == 0
    assert row.success == 0
