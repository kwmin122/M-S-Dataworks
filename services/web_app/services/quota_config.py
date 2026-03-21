"""Subscription plan quotas and feature gates.

Defines per-plan limits for usage metering. Plan defaults to "free" when
Organization.plan_tier is NULL or unrecognized.

Limit semantics:
  -1 = unlimited
   0 = feature disabled (always blocked)
  >0 = max count per period (month or day depending on key suffix)
"""
from __future__ import annotations

from typing import Any

PLAN_QUOTAS: dict[str, dict[str, Any]] = {
    "free": {
        "analyze_per_month": 5,
        "generate_per_month": 0,   # No generation on free
        "chat_per_day": 20,
        "features": {"studio_visible", "search", "analyze"},
    },
    "starter": {
        "analyze_per_month": 20,
        "generate_per_month": 10,
        "chat_per_day": 100,
        "features": {"studio_visible", "search", "analyze", "generate", "download"},
    },
    "pro": {
        "analyze_per_month": -1,   # unlimited
        "generate_per_month": 30,
        "chat_per_day": -1,        # unlimited
        "features": {
            "studio_visible", "search", "analyze", "generate",
            "relearn", "download", "alerts",
        },
    },
    "enterprise": {
        "analyze_per_month": -1,
        "generate_per_month": -1,
        "chat_per_day": -1,
        "features": {
            "studio_visible", "search", "analyze", "generate",
            "relearn", "download", "alerts", "admin_metrics",
        },
    },
}

# Map event_type -> quota key in PLAN_QUOTAS
_EVENT_TO_QUOTA_KEY: dict[str, str] = {
    "analyze": "analyze_per_month",
    "classify": "analyze_per_month",  # classify consumes analyze quota
    "generate": "generate_per_month",
}

# Human-readable labels for quota exceeded messages
_QUOTA_LABELS: dict[str, str] = {
    "analyze_per_month": "분석",
    "generate_per_month": "생성",
    "chat_per_day": "채팅",
}


def get_plan_quotas(plan: str) -> dict[str, Any]:
    """Return quotas for a plan tier, defaulting to free."""
    return PLAN_QUOTAS.get(plan or "free", PLAN_QUOTAS["free"])


def get_quota_key(event_type: str) -> str | None:
    """Map an event_type to its quota key, or None if not metered."""
    return _EVENT_TO_QUOTA_KEY.get(event_type)


def get_quota_label(quota_key: str) -> str:
    """Human-readable label for a quota key."""
    return _QUOTA_LABELS.get(quota_key, quota_key)
