"""LLM Middleware — shared logging, token tracking, error standardization.

Wraps any LLM call function to add observability without changing call semantics.
Existing call_with_retry is preserved (retry != middleware responsibility).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")

# GPT-4o-mini pricing (USD per 1M tokens, as of 2025-01)
_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


class LLMError(Exception):
    """Standardized LLM error with caller context."""

    def __init__(self, message: str, caller: str = "", original: Exception | None = None):
        super().__init__(message)
        self.caller = caller
        self.original = original


@dataclass
class LLMCallRecord:
    caller: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    success: bool
    error_message: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def estimated_cost_usd(self) -> float:
        pricing = _PRICING.get(self.model, _PRICING["gpt-4o-mini"])
        return (
            self.prompt_tokens * pricing["input"] / 1_000_000
            + self.completion_tokens * pricing["output"] / 1_000_000
        )


class LLMMiddleware:
    """Decorator-based middleware for LLM calls.

    Usage:
        mw = LLMMiddleware()
        wrapped = mw.wrap(openai_call_fn, caller_name="section_writer")
        result = wrapped(messages=[...])
    """

    def __init__(
        self,
        enable_logging: bool = True,
        enable_token_tracking: bool = True,
        enable_cache: bool = False,
    ):
        self.enable_logging = enable_logging
        self.enable_token_tracking = enable_token_tracking
        self.enable_cache = enable_cache
        self.records: list[LLMCallRecord] = []

    def wrap(self, fn: Callable[..., T], caller_name: str = "unknown") -> Callable[..., T]:
        """Wrap an LLM call function with logging and tracking."""

        def wrapped(*args: Any, **kwargs: Any) -> T:
            start = time.time()
            try:
                result = fn(*args, **kwargs)
                latency = (time.time() - start) * 1000

                # Extract usage if available
                prompt_tokens = 0
                completion_tokens = 0
                model = "gpt-4o-mini"
                usage = getattr(result, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                model_attr = getattr(result, "model", None)
                if model_attr:
                    model = model_attr

                record = LLMCallRecord(
                    caller=caller_name,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=round(latency, 1),
                    success=True,
                )
                self.records.append(record)

                if self.enable_logging:
                    logger.info(
                        "LLM [%s] %s: %d+%d tokens, %.0fms",
                        caller_name,
                        model,
                        prompt_tokens,
                        completion_tokens,
                        latency,
                    )

                return result

            except Exception as exc:
                latency = (time.time() - start) * 1000
                record = LLMCallRecord(
                    caller=caller_name,
                    model="gpt-4o-mini",
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_ms=round(latency, 1),
                    success=False,
                    error_message=str(exc),
                )
                self.records.append(record)

                if self.enable_logging:
                    logger.error("LLM [%s] FAILED: %s (%.0fms)", caller_name, exc, latency)

                raise LLMError(
                    f"LLM call failed in {caller_name}: {exc}",
                    caller=caller_name,
                    original=exc,
                ) from exc

        return wrapped  # type: ignore[return-value]

    def get_session_stats(self) -> dict[str, Any]:
        """Return aggregated stats for billing/monitoring."""
        success = [r for r in self.records if r.success]
        return {
            "total_calls": len(self.records),
            "successful_calls": len(success),
            "failed_calls": len(self.records) - len(success),
            "total_prompt_tokens": sum(r.prompt_tokens for r in self.records),
            "total_completion_tokens": sum(r.completion_tokens for r in self.records),
            "total_tokens": sum(r.total_tokens for r in self.records),
            "total_cost_usd": round(sum(r.estimated_cost_usd for r in self.records), 6),
            "avg_latency_ms": round(
                sum(r.latency_ms for r in success) / len(success), 1
            ) if success else 0,
            "by_caller": self._stats_by_caller(),
        }

    def _stats_by_caller(self) -> dict[str, dict[str, Any]]:
        callers: dict[str, list[LLMCallRecord]] = {}
        for r in self.records:
            callers.setdefault(r.caller, []).append(r)
        return {
            caller: {
                "calls": len(recs),
                "tokens": sum(r.total_tokens for r in recs),
                "cost_usd": round(sum(r.estimated_cost_usd for r in recs), 6),
            }
            for caller, recs in callers.items()
        }
