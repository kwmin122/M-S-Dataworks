"""Usage event tracking — emit telemetry for billing, observability, and performance."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.models.usage import UsageEvent
from services.web_app.services.quota_config import (
    get_plan_quotas,
    get_quota_key,
    get_quota_label,
)

_VALID_EVENT_TYPES = frozenset(
    {"analyze", "classify", "generate", "upload", "search", "relearn", "download"}
)
_VALID_STATUSES = frozenset({"success", "failure", "timeout"})

# Approximate token pricing (USD per 1K tokens, input+output blended)
_MODEL_PRICING: dict[str, float] = {
    "gpt-4o": 0.005,
    "gpt-4o-mini": 0.00015,
    "gpt-4": 0.03,
    "gpt-3.5-turbo": 0.0005,
}


async def emit_usage_event(
    db: AsyncSession,
    *,
    org_id: str,
    event_type: str,
    status: str,
    user_id: str | None = None,
    project_id: str | None = None,
    doc_type: str | None = None,
    model_name: str | None = None,
    token_count: int | None = None,
    estimated_cost_usd: float | None = None,
    duration_ms: int | None = None,
    error_message: str | None = None,
    detail_json: dict | None = None,
) -> None:
    """Emit a usage event to the usage_events table.

    Validates event_type and status against allowed values, auto-computes
    estimated_cost_usd from token_count + model_name when not provided,
    and truncates error_message to 500 chars.

    Does NOT commit — caller controls the transaction boundary.
    """
    if event_type not in _VALID_EVENT_TYPES:
        raise ValueError(f"Invalid event_type: {event_type}")
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    # Auto-compute cost if token_count and model_name provided but cost not
    if estimated_cost_usd is None and token_count and model_name:
        rate = _MODEL_PRICING.get(model_name, 0)
        if rate:
            estimated_cost_usd = round(rate * token_count / 1000, 6)

    event = UsageEvent(
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        event_type=event_type,
        doc_type=doc_type,
        model_name=model_name,
        token_count=token_count,
        estimated_cost_usd=estimated_cost_usd,
        duration_ms=duration_ms,
        status=status,
        error_message=error_message[:500] if error_message else None,
        detail_json=detail_json,
    )
    # Use savepoint to isolate — if usage_events table doesn't exist yet,
    # the main transaction is not poisoned.
    try:
        async with db.begin_nested():
            db.add(event)
    except Exception:
        pass  # Table may not exist yet in production; graceful degradation
    # Don't commit — caller controls transaction


async def check_quota(
    db: AsyncSession,
    org_id: str,
    event_type: str,
    plan: str = "free",
) -> tuple[bool, str]:
    """Check if org is within quota for this event_type.

    Returns (allowed, message). If not allowed, message explains why.
    Checks against PLAN_QUOTAS for the given plan tier.

    For monthly quotas: counts successful events in the current calendar month.
    For daily quotas: counts successful events today (UTC).

    Returns (True, "") if:
      - event_type is not metered
      - quota limit is -1 (unlimited)
      - current count < limit
    """
    quota_key = get_quota_key(event_type)
    if quota_key is None:
        return True, ""

    plan_limits = get_plan_quotas(plan)
    limit = plan_limits.get(quota_key)
    if limit is None:
        return True, ""

    # Unlimited
    if limit == -1:
        return True, ""

    # Zero means feature disabled on this plan
    if limit == 0:
        label = get_quota_label(quota_key)
        return False, f"{label} 기능은 현재 플랜에서 사용할 수 없습니다. PRO 플랜으로 업그레이드하세요."

    # Determine period filter
    now = datetime.now(timezone.utc)
    if quota_key.endswith("_per_month"):
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif quota_key.endswith("_per_day"):
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # Unknown period suffix — allow (don't block on misconfiguration)
        return True, ""

    # For classify, count both analyze + classify events (shared quota)
    if event_type == "classify":
        type_filter = UsageEvent.event_type.in_(["analyze", "classify"])
    else:
        type_filter = UsageEvent.event_type == event_type

    result = await db.execute(
        select(func.count(UsageEvent.id)).where(
            UsageEvent.org_id == org_id,
            type_filter,
            UsageEvent.status == "success",
            UsageEvent.created_at >= period_start,
        )
    )
    count = result.scalar_one()

    if count >= limit:
        label = get_quota_label(quota_key)
        period_label = "이번 달" if quota_key.endswith("_per_month") else "오늘"
        return (
            False,
            f"{period_label} {label} 횟수({limit}회)를 초과했습니다. PRO 플랜으로 업그레이드하세요.",
        )

    return True, ""


async def enforce_quota(
    db: AsyncSession,
    org_id: str,
    event_type: str,
) -> None:
    """Load org plan_tier from DB and enforce quota. Raises HTTPException(402) if exceeded.

    Designed for use in API endpoints — wraps check_quota with org lookup.
    Gracefully does nothing if the Organization row cannot be loaded (e.g. dev mode).
    Set BID_QUOTA_DISABLED=1 to skip quota enforcement (testing/development).
    """
    import os
    if os.environ.get("BID_QUOTA_DISABLED"):
        return
    from services.web_app.db.models.org import Organization

    result = await db.execute(
        select(Organization.plan_tier).where(Organization.id == org_id)
    )
    plan_tier = result.scalar_one_or_none() or "free"

    allowed, message = await check_quota(db, org_id, event_type, plan_tier)
    if not allowed:
        from fastapi import HTTPException

        raise HTTPException(status_code=402, detail=message)
