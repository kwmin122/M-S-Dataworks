"""Usage event tracking — emit telemetry for billing, observability, and performance."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.models.usage import UsageEvent

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
    db.add(event)
    # Don't commit — caller controls transaction
