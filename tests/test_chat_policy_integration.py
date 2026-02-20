from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chat_router import (  # noqa: E402
    RouteIntent,
    ChatPolicy,
    RouteDecision,
    apply_context_policy,
    build_policy_response,
)


def test_unknown_query_returns_clarify_message() -> None:
    decision = RouteDecision(
        intent=RouteIntent.UNKNOWN,
        confidence=0.1,
        policy=ChatPolicy.ASK_CLARIFY,
        reason="모호",
    )
    response = build_policy_response(decision)
    assert "명확" in response or "의도" in response


def test_domain_query_without_context_blocks() -> None:
    decision = RouteDecision(
        intent=RouteIntent.DOMAIN_RFX,
        confidence=0.95,
        policy=ChatPolicy.ALLOW,
        reason="도메인",
    )
    updated = apply_context_policy(
        decision=decision,
        has_context=False,
        relevance_score=0.0,
        min_relevance_score=0.0,
    )
    assert updated.policy == ChatPolicy.BLOCK_INSUFFICIENT_CONTEXT
    assert "문맥" in updated.reason or "근거" in updated.reason


def test_relevance_threshold_blocks_when_enabled() -> None:
    decision = RouteDecision(
        intent=RouteIntent.DOC_QA,
        confidence=0.9,
        policy=ChatPolicy.ALLOW,
        reason="문서 질의",
    )
    updated = apply_context_policy(
        decision=decision,
        has_context=True,
        relevance_score=0.31,
        min_relevance_score=0.5,
    )
    assert updated.policy == ChatPolicy.BLOCK_INSUFFICIENT_CONTEXT


def test_relevance_threshold_skipped_when_zero() -> None:
    decision = RouteDecision(
        intent=RouteIntent.DOC_QA,
        confidence=0.9,
        policy=ChatPolicy.ALLOW,
        reason="문서 질의",
    )
    updated = apply_context_policy(
        decision=decision,
        has_context=True,
        relevance_score=0.01,
        min_relevance_score=0.0,
    )
    assert updated.policy == ChatPolicy.ALLOW


def test_offtopic_policy_message_is_available_without_api_key() -> None:
    decision = RouteDecision(
        intent=RouteIntent.SMALL_TALK_OFFTOPIC,
        confidence=0.99,
        policy=ChatPolicy.BLOCK_OFFTOPIC,
        reason="오프토픽",
    )
    response = build_policy_response(decision)
    assert "입찰/RFx 문서 분석 전용" in response
