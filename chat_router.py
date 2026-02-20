"""
질의 라우팅/정책 모듈.

역할:
1) 키워드 프리필터로 명백한 오프토픽/도메인 질의를 빠르게 분기
2) 모호한 질의만 LLM Structured Outputs로 의도 분류
3) 정책(ALLOW/BLOCK/CLARIFY) 결정을 일관되게 반환
4) 개인정보 최소화된 텔레메트리(JSONL) 기록
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class RouteIntent(str, Enum):
    """질의 의도 분류"""

    DOMAIN_RFX = "DOMAIN_RFX"
    DOC_QA = "DOC_QA"
    SMALL_TALK_OFFTOPIC = "SMALL_TALK_OFFTOPIC"
    UNKNOWN = "UNKNOWN"
    UNSAFE = "UNSAFE"


class ChatPolicy(str, Enum):
    """최종 응답 정책"""

    ALLOW = "ALLOW"
    BLOCK_OFFTOPIC = "BLOCK_OFFTOPIC"
    BLOCK_INSUFFICIENT_CONTEXT = "BLOCK_INSUFFICIENT_CONTEXT"
    BLOCK_UNSAFE = "BLOCK_UNSAFE"
    ASK_CLARIFY = "ASK_CLARIFY"


DEFAULT_SUGGESTED_QUESTIONS: list[str] = [
    "우리 회사 기준으로 미충족 항목 3개만 알려줘",
    "마감 전에 준비할 서류 체크리스트를 만들어줘",
    "가장 위험한 항목과 대응안을 짧게 정리해줘",
    "근거 페이지를 포함해 핵심 요약을 보여줘",
]


OFFTOPIC_KEYWORDS: tuple[str, ...] = (
    "배고파",
    "점심",
    "저녁",
    "맛집",
    "날씨",
    "심심",
    "연애",
    "게임",
    "노래",
    "영화",
    "운세",
)


DOMAIN_KEYWORDS: tuple[str, ...] = (
    "입찰",
    "rfx",
    "rfp",
    "rfq",
    "rfi",
    "제안요청",
    "공고",
    "자격요건",
    "평가기준",
    "가점",
    "감점",
    "iso",
    "실적",
    "제출서류",
    "마감일",
    "발주기관",
    "요약",
    "근거",
    "pdf",
    "페이지",
)

COMPANY_DOC_KEYWORDS: tuple[str, ...] = (
    "우리 회사",
    "회사명",
    "회사 이름",
    "회사 정보",
    "대표",
    "사업자등록",
    "연락처",
    "보유 인증",
    "핵심 역량",
)


UNSAFE_KEYWORDS: tuple[str, ...] = (
    "해킹",
    "악성코드",
    "불법",
    "사기",
    "도용",
)


ROUTER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {
            "type": "string",
            "enum": [intent.value for intent in RouteIntent],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reason": {"type": "string"},
        "suggested_questions": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 0,
            "maxItems": 4,
        },
    },
    "required": ["intent", "confidence", "reason", "suggested_questions"],
}


@dataclass
class RouteDecision:
    """라우팅 최종 결과"""

    intent: RouteIntent
    confidence: float
    policy: ChatPolicy
    reason: str
    suggested_questions: list[str] = field(default_factory=lambda: DEFAULT_SUGGESTED_QUESTIONS[:])
    source: str = "prefilter"  # prefilter|llm|fallback
    llm_called: bool = False


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _safe_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed))


def _parse_intent(raw_intent: Any) -> RouteIntent:
    normalized = str(raw_intent or "").strip().upper()
    for intent in RouteIntent:
        if normalized == intent.value:
            return intent
    return RouteIntent.UNKNOWN


def _map_policy(
    intent: RouteIntent,
    confidence: float,
    confidence_threshold: float,
    offtopic_strict: bool,
) -> ChatPolicy:
    if intent == RouteIntent.UNSAFE:
        return ChatPolicy.BLOCK_UNSAFE
    if intent == RouteIntent.SMALL_TALK_OFFTOPIC:
        return ChatPolicy.BLOCK_OFFTOPIC if offtopic_strict else ChatPolicy.ASK_CLARIFY
    if intent == RouteIntent.UNKNOWN:
        return ChatPolicy.ASK_CLARIFY
    if confidence < confidence_threshold:
        return ChatPolicy.ASK_CLARIFY
    return ChatPolicy.ALLOW


def _build_prefilter_decision(message: str, offtopic_strict: bool) -> RouteDecision | None:
    normalized = _normalize_text(message)
    if not normalized:
        return RouteDecision(
            intent=RouteIntent.UNKNOWN,
            confidence=0.0,
            policy=ChatPolicy.ASK_CLARIFY,
            reason="빈 입력입니다.",
            source="prefilter",
        )

    if _contains_any(normalized, UNSAFE_KEYWORDS):
        return RouteDecision(
            intent=RouteIntent.UNSAFE,
            confidence=0.99,
            policy=ChatPolicy.BLOCK_UNSAFE,
            reason="안전 정책 키워드가 감지되었습니다.",
            source="prefilter",
        )

    if _contains_any(normalized, OFFTOPIC_KEYWORDS):
        return RouteDecision(
            intent=RouteIntent.SMALL_TALK_OFFTOPIC,
            confidence=0.99,
            policy=ChatPolicy.BLOCK_OFFTOPIC if offtopic_strict else ChatPolicy.ASK_CLARIFY,
            reason="일상 대화/비업무 키워드가 감지되었습니다.",
            source="prefilter",
        )

    if _contains_any(normalized, COMPANY_DOC_KEYWORDS):
        return RouteDecision(
            intent=RouteIntent.DOC_QA,
            confidence=0.93,
            policy=ChatPolicy.ALLOW,
            reason="회사/문서 질의 키워드가 감지되었습니다.",
            source="prefilter",
        )

    if _contains_any(normalized, DOMAIN_KEYWORDS):
        return RouteDecision(
            intent=RouteIntent.DOMAIN_RFX,
            confidence=0.92,
            policy=ChatPolicy.ALLOW,
            reason="입찰/RFx 도메인 키워드가 감지되었습니다.",
            source="prefilter",
        )

    return None


def _classify_intent_with_llm(message: str, api_key: str, model: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    system_prompt = """너는 입찰/RFx 챗봇용 질의 라우터다.
반드시 JSON 스키마로만 응답한다.

의도 정의:
- DOMAIN_RFX: 입찰 자격/평가/문서 분석/GO-NO-GO 관련 질의
- DOC_QA: 업로드된 문서 내용 질의(요약/근거/페이지 확인)
- SMALL_TALK_OFFTOPIC: 업무 외 잡담/일상 질의
- UNKNOWN: 의도 불명확/짧고 모호한 질의
- UNSAFE: 불법/악성 목적 질의
"""
    response = client.chat.completions.create(
        model=model,
        temperature=0.0,
        max_tokens=220,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "chat_route_decision",
                "strict": True,
                "schema": ROUTER_JSON_SCHEMA,
            },
        },
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"질문: {message}"},
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("라우터 응답이 객체 형식이 아닙니다.")
    return parsed


def route_user_query(
    message: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    confidence_threshold: float = 0.65,
    offtopic_strict: bool = True,
) -> RouteDecision:
    """질의를 정책 가능한 형태로 라우팅한다."""
    prefiltered = _build_prefilter_decision(message, offtopic_strict=offtopic_strict)
    if prefiltered:
        return prefiltered

    if not api_key:
        return RouteDecision(
            intent=RouteIntent.UNKNOWN,
            confidence=0.0,
            policy=ChatPolicy.ALLOW,
            reason="API 키 없음: 오프토픽/위험 질의가 아니므로 기본 허용 후 문맥 정책으로 검증합니다.",
            source="fallback",
            llm_called=False,
        )

    try:
        payload = _classify_intent_with_llm(message=message, api_key=api_key, model=model)
        intent = _parse_intent(payload.get("intent"))
        confidence = _safe_confidence(payload.get("confidence"))
        reason = str(payload.get("reason", "")).strip() or "LLM 분류 결과"
        suggested = payload.get("suggested_questions")
        if not isinstance(suggested, list):
            suggested = DEFAULT_SUGGESTED_QUESTIONS[:]
        else:
            suggested = [str(item).strip() for item in suggested if str(item).strip()][:4]
            if not suggested:
                suggested = DEFAULT_SUGGESTED_QUESTIONS[:]

        policy = _map_policy(
            intent=intent,
            confidence=confidence,
            confidence_threshold=confidence_threshold,
            offtopic_strict=offtopic_strict,
        )
        return RouteDecision(
            intent=intent,
            confidence=confidence,
            policy=policy,
            reason=reason,
            suggested_questions=suggested,
            source="llm",
            llm_called=True,
        )
    except Exception as exc:
        return RouteDecision(
            intent=RouteIntent.UNKNOWN,
            confidence=0.0,
            policy=ChatPolicy.ASK_CLARIFY,
            reason=f"라우터 분류 실패: {exc}",
            source="fallback",
            llm_called=True,
        )


def apply_context_policy(
    decision: RouteDecision,
    has_context: bool,
    relevance_score: float,
    min_relevance_score: float,
) -> RouteDecision:
    """
    문맥 부족 정책 적용.
    - 라우터 정책이 ALLOW일 때만 문맥 부족 차단을 수행한다.
    - min_relevance_score <= 0 이면 점수 기반 차단 비활성이다.
    """
    if decision.policy != ChatPolicy.ALLOW:
        return decision

    if not has_context:
        return replace(
            decision,
            policy=ChatPolicy.BLOCK_INSUFFICIENT_CONTEXT,
            reason="회사/RFx 문서 문맥이 없어 근거 기반 답변이 불가능합니다.",
        )

    if min_relevance_score > 0.0 and relevance_score < min_relevance_score:
        return replace(
            decision,
            policy=ChatPolicy.BLOCK_INSUFFICIENT_CONTEXT,
            reason=(
                "관련 근거 점수가 임계값보다 낮습니다. "
                f"(score={relevance_score:.3f}, threshold={min_relevance_score:.3f})"
            ),
        )

    return decision


def build_policy_response(decision: RouteDecision) -> str:
    """정책별 사용자 안내 문구 생성"""
    if decision.policy == ChatPolicy.BLOCK_OFFTOPIC:
        return (
            "저는 **입찰/RFx 문서 분석 전용 어시스턴트**입니다.\n\n"
            "일상 대화 질문은 답변하지 않습니다. 아래 예시 질문으로 다시 요청해주세요."
        )
    if decision.policy == ChatPolicy.BLOCK_INSUFFICIENT_CONTEXT:
        return (
            "현재 질문에 답할 **근거 문맥이 부족**합니다.\n\n"
            "1) 회사 문서 또는 RFx 문서를 먼저 업로드하고\n"
            "2) 문서 기준 질문으로 다시 요청해주세요."
        )
    if decision.policy == ChatPolicy.BLOCK_UNSAFE:
        return "해당 요청은 안전 정책상 처리할 수 없습니다."
    if decision.policy == ChatPolicy.ASK_CLARIFY:
        return (
            "질문 의도를 명확히 파악하지 못했습니다.\n\n"
            "입찰/문서 중심으로 다시 질문해 주세요."
        )
    return ""


def write_router_telemetry(
    *,
    log_path: str,
    message: str,
    decision: RouteDecision,
    company_scores: list[float],
    rfx_scores: list[float],
    relevance_score: float,
    min_relevance_score: float,
    has_context: bool,
) -> None:
    """질의 원문 없이 라우팅 텔레메트리 기록"""
    normalized = _normalize_text(message)
    query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_hash": query_hash,
        "query_length": len(message or ""),
        "intent": decision.intent.value,
        "policy": decision.policy.value,
        "confidence": round(_safe_confidence(decision.confidence), 4),
        "reason": decision.reason,
        "source": decision.source,
        "llm_called": bool(decision.llm_called),
        "has_context": bool(has_context),
        "relevance_score": round(float(relevance_score), 4),
        "min_relevance_score": round(float(min_relevance_score), 4),
        "company_scores": [round(float(score), 4) for score in company_scores],
        "rfx_scores": [round(float(score), 4) for score in rfx_scores],
    }

    output_path = Path(log_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def default_router_log_path() -> str:
    return os.getenv(
        "CHAT_ROUTER_LOG_PATH",
        "./reports/router_telemetry.jsonl",
    )
