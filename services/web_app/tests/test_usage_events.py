"""UsageEvent model + usage_tracker tests. Requires PostgreSQL (BID_TEST_DATABASE_URL)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from services.web_app.db.models.org import Organization
from services.web_app.db.models.usage import UsageEvent
from services.web_app.services.usage_tracker import check_quota, emit_usage_event


# ---------------------------------------------------------------------------
# Helper: create an org for FK satisfaction
# ---------------------------------------------------------------------------
async def _make_org(db_session, name: str = "테스트") -> Organization:
    org = Organization(name=name)
    db_session.add(org)
    await db_session.flush()
    return org


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_usage_event_success(db_session):
    """Emit a usage event and verify all fields round-trip correctly."""
    org = await _make_org(db_session)

    await emit_usage_event(
        db_session,
        org_id=org.id,
        event_type="generate",
        status="success",
        user_id="user-1",
        doc_type="proposal",
        model_name="gpt-4o",
        token_count=1500,
        duration_ms=3200,
        detail_json={"sections": 5},
    )
    await db_session.flush()

    result = await db_session.execute(
        select(UsageEvent).where(UsageEvent.org_id == org.id)
    )
    evt = result.scalar_one()

    assert evt.event_type == "generate"
    assert evt.status == "success"
    assert evt.user_id == "user-1"
    assert evt.doc_type == "proposal"
    assert evt.model_name == "gpt-4o"
    assert evt.token_count == 1500
    assert evt.duration_ms == 3200
    assert evt.detail_json == {"sections": 5}
    assert evt.created_at is not None


@pytest.mark.asyncio
async def test_emit_usage_event_auto_cost(db_session):
    """When token_count + model_name provided but cost is None, auto-compute."""
    org = await _make_org(db_session)

    await emit_usage_event(
        db_session,
        org_id=org.id,
        event_type="analyze",
        status="success",
        model_name="gpt-4o",
        token_count=2000,
    )
    await db_session.flush()

    result = await db_session.execute(
        select(UsageEvent).where(UsageEvent.org_id == org.id)
    )
    evt = result.scalar_one()

    # gpt-4o rate = 0.005 per 1K tokens → 2000 tokens = 0.01
    assert evt.estimated_cost_usd == Decimal("0.010000")


@pytest.mark.asyncio
async def test_emit_usage_event_invalid_type(db_session):
    """Invalid event_type raises ValueError."""
    org = await _make_org(db_session)

    with pytest.raises(ValueError, match="Invalid event_type: bogus"):
        await emit_usage_event(
            db_session,
            org_id=org.id,
            event_type="bogus",
            status="success",
        )


@pytest.mark.asyncio
async def test_emit_usage_event_invalid_status(db_session):
    """Invalid status raises ValueError."""
    org = await _make_org(db_session)

    with pytest.raises(ValueError, match="Invalid status: unknown"):
        await emit_usage_event(
            db_session,
            org_id=org.id,
            event_type="generate",
            status="unknown",
        )


@pytest.mark.asyncio
async def test_emit_usage_event_error_truncation(db_session):
    """Error messages longer than 500 chars are truncated to 500."""
    org = await _make_org(db_session)

    long_error = "E" * 600

    await emit_usage_event(
        db_session,
        org_id=org.id,
        event_type="generate",
        status="failure",
        error_message=long_error,
    )
    await db_session.flush()

    result = await db_session.execute(
        select(UsageEvent).where(UsageEvent.org_id == org.id)
    )
    evt = result.scalar_one()

    assert len(evt.error_message) == 500
    assert evt.error_message == "E" * 500


# ---------------------------------------------------------------------------
# Quota check tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_quota_within_limit(db_session):
    """3/5 analyze events used on free plan → still allowed."""
    org = await _make_org(db_session, name="쿼터-이내")

    # Emit 3 successful analyze events
    for _ in range(3):
        await emit_usage_event(
            db_session,
            org_id=org.id,
            event_type="analyze",
            status="success",
        )
    await db_session.flush()

    allowed, message = await check_quota(db_session, org.id, "analyze", "free")
    assert allowed is True
    assert message == ""


@pytest.mark.asyncio
async def test_check_quota_exceeded(db_session):
    """5/5 analyze events used on free plan → blocked with message."""
    org = await _make_org(db_session, name="쿼터-초과")

    # Emit 5 successful analyze events (free limit)
    for _ in range(5):
        await emit_usage_event(
            db_session,
            org_id=org.id,
            event_type="analyze",
            status="success",
        )
    await db_session.flush()

    allowed, message = await check_quota(db_session, org.id, "analyze", "free")
    assert allowed is False
    assert "초과했습니다" in message
    assert "5회" in message
    assert "업그레이드" in message


@pytest.mark.asyncio
async def test_check_quota_unlimited(db_session):
    """Pro plan with -1 (unlimited) analyze → always allowed."""
    org = await _make_org(db_session, name="쿼터-무제한")

    # Emit many events — should never hit limit
    for _ in range(50):
        await emit_usage_event(
            db_session,
            org_id=org.id,
            event_type="analyze",
            status="success",
        )
    await db_session.flush()

    allowed, message = await check_quota(db_session, org.id, "analyze", "pro")
    assert allowed is True
    assert message == ""


@pytest.mark.asyncio
async def test_check_quota_free_generate_blocked(db_session):
    """Free plan, generate → always blocked (limit 0)."""
    org = await _make_org(db_session, name="쿼터-생성차단")

    # Even with zero events, generate is blocked on free
    allowed, message = await check_quota(db_session, org.id, "generate", "free")
    assert allowed is False
    assert "사용할 수 없습니다" in message
    assert "업그레이드" in message


@pytest.mark.asyncio
async def test_check_quota_failure_events_not_counted(db_session):
    """Failed events should not count toward quota."""
    org = await _make_org(db_session, name="쿼터-실패무시")

    # Emit 5 failures + 2 successes
    for _ in range(5):
        await emit_usage_event(
            db_session,
            org_id=org.id,
            event_type="analyze",
            status="failure",
        )
    for _ in range(2):
        await emit_usage_event(
            db_session,
            org_id=org.id,
            event_type="analyze",
            status="success",
        )
    await db_session.flush()

    # Free limit is 5 — only 2 successes, so should be allowed
    allowed, message = await check_quota(db_session, org.id, "analyze", "free")
    assert allowed is True


@pytest.mark.asyncio
async def test_check_quota_unmetered_event(db_session):
    """Unmetered event types (e.g. upload) are always allowed."""
    org = await _make_org(db_session, name="쿼터-비측정")

    allowed, message = await check_quota(db_session, org.id, "upload", "free")
    assert allowed is True
    assert message == ""
