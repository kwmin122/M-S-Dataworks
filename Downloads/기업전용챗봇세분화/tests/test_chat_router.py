from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chat_router import (  # noqa: E402
    RouteIntent,
    ChatPolicy,
    RouteDecision,
    route_user_query,
    apply_context_policy,
    write_router_telemetry,
    _build_prefilter_decision,
)


def test_prefilter_offtopic_blocks_without_llm() -> None:
    decision = route_user_query(
        message="배고파 점심 추천해줘",
        api_key="",
    )
    assert decision.intent == RouteIntent.SMALL_TALK_OFFTOPIC
    assert decision.policy == ChatPolicy.BLOCK_OFFTOPIC
    assert decision.llm_called is False


def test_prefilter_domain_allows_without_llm() -> None:
    decision = route_user_query(
        message="이 RFx 필수 자격요건 요약해줘",
        api_key="",
    )
    assert decision.intent == RouteIntent.DOMAIN_RFX
    assert decision.policy == ChatPolicy.ALLOW
    assert decision.llm_called is False


def test_prefilter_company_profile_question_allows_without_llm() -> None:
    decision = route_user_query(
        message="현재 우리 회사 이름은 뭐야?",
        api_key="",
    )
    assert decision.intent == RouteIntent.DOC_QA
    assert decision.policy == ChatPolicy.ALLOW
    assert decision.llm_called is False


def test_context_policy_blocks_when_no_context() -> None:
    decision = RouteDecision(
        intent=RouteIntent.DOMAIN_RFX,
        confidence=0.9,
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


def test_context_policy_respects_disabled_threshold() -> None:
    decision = RouteDecision(
        intent=RouteIntent.DOC_QA,
        confidence=0.9,
        policy=ChatPolicy.ALLOW,
        reason="문서질의",
    )
    updated = apply_context_policy(
        decision=decision,
        has_context=True,
        relevance_score=0.05,
        min_relevance_score=0.0,
    )
    assert updated.policy == ChatPolicy.ALLOW


def test_write_router_telemetry_omits_raw_query(tmp_path: Path) -> None:
    log_path = tmp_path / "router.jsonl"
    decision = RouteDecision(
        intent=RouteIntent.UNKNOWN,
        confidence=0.2,
        policy=ChatPolicy.ASK_CLARIFY,
        reason="모호",
    )
    write_router_telemetry(
        log_path=str(log_path),
        message="배고파요 오늘 점심 뭐 먹지?",
        decision=decision,
        company_scores=[0.1, 0.2],
        rfx_scores=[0.3],
        relevance_score=0.3,
        min_relevance_score=0.0,
        has_context=False,
    )
    line = log_path.read_text(encoding="utf-8").strip()
    assert line
    assert "배고파요" not in line
    assert "query_hash" in line


# ────────────────────────────────────────────────────────────
# 프리필터 직접 테스트 (no-key 의존 없음)
# ────────────────────────────────────────────────────────────

def test_prefilter_blocks_offtopic_directly() -> None:
    """_build_prefilter_decision이 오프토픽 즉시 차단"""
    result = _build_prefilter_decision("배고파 맛집 추천해줘", offtopic_strict=True)
    assert result is not None
    assert result.policy == ChatPolicy.BLOCK_OFFTOPIC


def test_prefilter_allows_rfx_domain() -> None:
    """자격요건/RFx 키워드 → 프리필터 ALLOW"""
    result = _build_prefilter_decision("이 RFx 자격요건 분석해줘", offtopic_strict=True)
    assert result is not None
    assert result.policy == ChatPolicy.ALLOW


def test_prefilter_allows_company_doc() -> None:
    """회사 정보 키워드 → 프리필터 ALLOW"""
    result = _build_prefilter_decision("우리 회사 이름 알려줘", offtopic_strict=True)
    assert result is not None
    assert result.policy == ChatPolicy.ALLOW


def test_prefilter_returns_none_for_unknown() -> None:
    """키워드 없는 질문 → None 반환 (LLM으로 넘겨야 함)"""
    result = _build_prefilter_decision("사업 기간이 어떻게 돼?", offtopic_strict=True)
    assert result is None


def test_llm_classifies_business_query_correctly() -> None:
    """LLM mock으로 업무 질의가 ALLOW로 분류되는지 확인"""
    from unittest.mock import patch

    mock_payload = {
        "intent": "DOMAIN_RFX",
        "confidence": 0.92,
        "reason": "입찰 관련 질의",
        "suggested_questions": [],
    }
    with patch("chat_router._classify_intent_with_llm", return_value=mock_payload):
        decision = route_user_query(
            message="사업 기간이 어떻게 돼?",
            api_key="dummy-key-for-test",
        )
    assert decision.policy == ChatPolicy.ALLOW
    assert decision.llm_called is True
