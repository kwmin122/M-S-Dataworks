"""ReAct Chat Loop — Reasoning + Acting pattern for Chat RAG.

Wraps the existing Tool Use call with a max-3-turn loop.
Early exit when LLM provides a direct answer (document_qa, general_response, etc.).
Re-search with LLM-generated query when need_more_context is triggered.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

# Ensure project root + rag_engine are on sys.path
_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
_RAG = os.path.join(_ROOT, "rag_engine")
for _p in (_ROOT, _RAG):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from chat_tools import CHAT_TOOLS, TOOL_USE_SYSTEM_PROMPT, parse_tool_call_result
from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT
from openai import OpenAI

logger = logging.getLogger(__name__)


def react_chat_loop(
    *,
    api_key: str,
    message: str,
    company_context_text: str,
    rfx_context_text: str,
    session: Any,
    max_turns: int = 3,
) -> tuple[str, str, list[dict[str, Any]]]:
    """ReAct loop: Reason → Act → Observe → Repeat (max 3 turns).

    Returns (tool_name, answer, references).
    Most queries resolve in Turn 1 (early exit).
    """
    current_company_ctx = company_context_text
    current_rfx_ctx = rfx_context_text
    current_message = message

    for turn in range(max_turns - 1):  # Reserve last turn for forced answer
        tool_name, answer, refs = _single_turn(
            api_key=api_key,
            message=current_message,
            company_context_text=current_company_ctx,
            rfx_context_text=current_rfx_ctx,
            session=session,
            include_need_more=True,
        )

        if tool_name != "need_more_context":
            logger.info("ReAct resolved in turn %d: %s", turn + 1, tool_name)
            return tool_name, answer, refs

        # Observation: need more context
        suggested_query = answer  # answer field carries suggested_query
        scope = refs[0].get("scope", "both") if refs else "both"
        reason = refs[0].get("reason", "") if refs else ""
        logger.info(
            "ReAct turn %d: need_more_context (reason=%s, query=%s, scope=%s)",
            turn + 1, reason, suggested_query, scope,
        )

        # Re-search with suggested query
        current_company_ctx, current_rfx_ctx = _rebuild_context(
            session=session,
            query=suggested_query,
            scope=scope,
        )
        current_message = f"{message}\n\n[이전 검색에서 불충분했던 이유: {reason}]"

    # Final turn: forced answer (no need_more_context tool)
    return _force_final_answer(
        api_key=api_key,
        message=current_message,
        company_context_text=current_company_ctx,
        rfx_context_text=current_rfx_ctx,
        session=session,
    )


def _single_turn(
    *,
    api_key: str,
    message: str,
    company_context_text: str,
    rfx_context_text: str,
    session: Any,
    include_need_more: bool = True,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Execute one Tool Use call."""
    tools = CHAT_TOOLS if include_need_more else [
        t for t in CHAT_TOOLS if t["function"]["name"] != "need_more_context"
    ]

    # Build system prompt with context
    matching_context = ""
    if hasattr(session, "latest_matching_result") and session.latest_matching_result:
        m = session.latest_matching_result
        matching_context = (
            f"적합도: {m.overall_score:.0f}%, 추천: {m.recommendation}, "
            f"충족/부분/미충족: {m.met_count}/{m.partially_met_count}/{m.not_met_count}"
        )

    rfx_meta = ""
    if hasattr(session, "latest_rfx_analysis") and session.latest_rfx_analysis:
        a = session.latest_rfx_analysis
        rfx_meta = f"공고명: {a.title}, 발주기관: {a.issuing_org}, 마감일: {a.deadline}"

    ctx_parts: list[str] = []
    if company_context_text:
        ctx_parts.append(f"\n### 회사 정보\n{company_context_text}")
    if rfx_context_text:
        ctx_parts.append(f"\n### RFx 원문\n{rfx_context_text}")
    if rfx_meta:
        ctx_parts.append(f"\n### RFx 메타\n{rfx_meta}")
    if matching_context:
        ctx_parts.append(f"\n### 매칭 요약\n{matching_context}")
    if not ctx_parts:
        ctx_parts.append("\n### 문서 컨텍스트: 없음")

    full_system = TOOL_USE_SYSTEM_PROMPT + "\n".join(ctx_parts)

    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key, timeout=LLM_DEFAULT_TIMEOUT)

    def _do_call():
        return client.chat.completions.create(
            model=model,
            max_tokens=4096,
            temperature=0.3,
            tools=tools,
            tool_choice="required",
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": message},
            ],
        )

    response = call_with_retry(_do_call)
    return parse_tool_call_result(response.choices[0].message)


def _rebuild_context(
    session: Any,
    query: str,
    scope: str,
) -> tuple[str, str]:
    """Re-search RAG with the LLM-suggested query."""
    company_text = ""
    rfx_text = ""

    try:
        if scope in ("company", "both") and hasattr(session, "rag_engine"):
            results = session.rag_engine.search(query, top_k=12)
            if results:
                chunks = []
                for doc, meta in results:
                    src = meta.get("source_file", "unknown")
                    page = meta.get("page_number", "?")
                    chunks.append(f"[{src}, 페이지 {page}]\n{doc}")
                company_text = "\n---\n".join(chunks)

        if scope in ("rfx", "both") and hasattr(session, "rfx_rag_engine"):
            results = session.rfx_rag_engine.search(query, top_k=12)
            if results:
                chunks = []
                for doc, meta in results:
                    src = meta.get("source_file", "unknown")
                    page = meta.get("page_number", "?")
                    chunks.append(f"[{src}, 페이지 {page}]\n{doc}")
                rfx_text = "\n---\n".join(chunks)
    except Exception as exc:
        logger.warning("ReAct rebuild_context error: %s", exc)

    return company_text, rfx_text


def _force_final_answer(
    *,
    api_key: str,
    message: str,
    company_context_text: str,
    rfx_context_text: str,
    session: Any,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Final turn without need_more_context — must give direct answer."""
    return _single_turn(
        api_key=api_key,
        message=message,
        company_context_text=company_context_text,
        rfx_context_text=rfx_context_text,
        session=session,
        include_need_more=False,
    )
