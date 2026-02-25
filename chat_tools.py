"""LLM Tool Use 기반 채팅 라우팅 도구 정의."""
from __future__ import annotations

import json
from typing import Any

CHAT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "document_qa",
            "description": (
                "사용자가 업로드한 문서(RFx/입찰공고/회사문서) 내용에 대해 질문할 때 사용. "
                "자격요건 요약, 미충족 항목, 핵심 포인트, 체크리스트, 근거 페이지, "
                "평가기준, 마감일, 준비서류, 리스크, GO/NO-GO 등 문서 기반 모든 질의."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string", "description": "한국어 답변"},
                    "references": {
                        "type": "array",
                        "maxItems": 10,
                        "description": "RFx 원문 참조 (최대 10개)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "page": {
                                    "type": "integer",
                                    "description": "RFx 원문 페이지 번호",
                                },
                                "text": {
                                    "type": "string",
                                    "description": "RFx 원문 발췌 (의역 금지)",
                                },
                            },
                            "required": ["page", "text"],
                        },
                    },
                },
                "required": ["answer", "references"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "general_response",
            "description": (
                "문서 컨텍스트 불필요한 일반 대화. 인사, 감사, 사용법 안내, 입찰 일반 지식. "
                "일상 잡담(날씨, 맛집 등)에는 정중히 거절하고 업무 질문 유도."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "한국어 답변",
                    },
                },
                "required": ["answer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bid_search",
            "description": "새 공고 검색 요청. 예: '소프트웨어 공고 찾아줘'",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "검색 기능 안내 메시지",
                    },
                },
                "required": ["answer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bid_analyze",
            "description": "새 문서/공고 분석 요청. 예: '이 공고 분석해줘', '새 문서 올리고 싶어'",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "분석 기능 안내 메시지",
                    },
                },
                "required": ["answer"],
            },
        },
    },
]


TOOL_USE_SYSTEM_PROMPT = """당신은 KiraBot, 공공조달·입찰 전문 AI 어시스턴트입니다.

## 역할
사용자가 업로드한 RFx(입찰공고/제안요청서) 및 회사 문서를 기반으로 자격요건 분석, GO/NO-GO 판단, 체크리스트, 근거 확인 등을 도와줍니다.

## 도구 사용 규칙
1. 문서 컨텍스트가 있고 질문이 문서 관련 → document_qa
2. 문서 불필요한 일반 대화/인사/안내 → general_response
3. 공고 검색 요청 → bid_search
4. 새 문서 분석 요청 → bid_analyze

## document_qa 규칙
- 사용자가 요약/정리/목록을 요청하면 컨텍스트에 있는 **모든 관련 항목**을 빠짐없이 답변할 것
- "핵심 요건 3개" 같은 요청에는 반드시 해당 개수만큼 항목을 찾아서 답변
- 컨텍스트에 정보가 있으면 **반드시** 그 내용을 인용하여 답변 (절대 "확인할 수 없습니다" 금지)
- references.page = RFx 원문 실제 페이지 번호만
- references.text = RFx 원문 그대로 발췌 (의역 금지, 핵심 문장 전체를 포함)
- 회사 정보는 references에 넣지 말 것
- 근거 부족 시 답변에 명시
- 회사 정보 질문이면 회사 컨텍스트 우선 (references 빈 배열 허용)

## general_response 규칙
- 업무 외 잡담에는 정중히 거절 + 입찰 관련 질문 유도
- 안전하지 않은 요청은 즉시 거절
- 한국어, 3~4문장 이내"""


def parse_tool_call_result(
    message: Any,
) -> tuple[str, str, list[dict[str, Any]]]:
    """OpenAI tool_calls 응답 파싱. Returns (tool_name, answer, references)."""
    tool_calls = message.tool_calls
    if not tool_calls:
        return "general_response", (message.content or "").strip(), []

    call = tool_calls[0]
    tool_name = call.function.name
    try:
        args = json.loads(call.function.arguments)
    except (json.JSONDecodeError, TypeError):
        args = {}

    answer = str(args.get("answer", "")).strip()
    references: list[dict[str, Any]] = []
    if tool_name == "document_qa":
        for ref in (args.get("references") or [])[:10]:
            if not isinstance(ref, dict):
                continue
            try:
                page = int(ref.get("page", 0))
            except (TypeError, ValueError):
                page = 0
            if page <= 0:
                continue
            references.append(
                {"page": page, "text": str(ref.get("text", "")).strip()}
            )

    return tool_name, answer, references
