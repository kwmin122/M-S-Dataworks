"""PPT Slide Planner — 슬라이드 구성 + 예상질문 생성.

공공조달 PT 표준 구성으로 슬라이드 배분하고 예상질문/모범답변을 생성.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT
from phase2_models import SlideType, SlideContent, QnaPair

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 표준 슬라이드 구조 (공공조달 PT)
# ---------------------------------------------------------------------------

DEFAULT_SLIDE_STRUCTURE: list[dict[str, Any]] = [
    {"name": "표지", "type": SlideType.COVER, "fixed": True, "count": 1},
    {"name": "목차", "type": SlideType.TOC, "fixed": True, "count": 1},
    {"name": "01 사업 이해", "type": SlideType.DIVIDER, "fixed": True, "count": 1},
    {"name": "사업 이해", "type": SlideType.CONTENT, "ratio": 0.15},
    {"name": "02 추진 전략", "type": SlideType.DIVIDER, "fixed": True, "count": 1},
    {"name": "추진 전략", "type": SlideType.CONTENT, "ratio": 0.20},
    {"name": "03 기술 방안", "type": SlideType.DIVIDER, "fixed": True, "count": 1},
    {"name": "기술 방안", "type": SlideType.CONTENT, "ratio": 0.25},
    {"name": "수행 일정", "type": SlideType.TIMELINE, "fixed": True, "count": 1},
    {"name": "투입 인력", "type": SlideType.TEAM, "fixed": True, "count": 1},
    {"name": "유사 실적", "type": SlideType.TABLE, "fixed": True, "count": 1},
    {"name": "04 품질/보안", "type": SlideType.DIVIDER, "fixed": True, "count": 1},
    {"name": "품질/보안", "type": SlideType.CONTENT, "ratio": 0.10},
    {"name": "기대 효과", "type": SlideType.BULLET, "fixed": True, "count": 1},
    {"name": "Q&A", "type": SlideType.QNA, "fixed": True, "count": 1},
    {"name": "마무리", "type": SlideType.CLOSING, "fixed": True, "count": 1},
]


# LLM 응답에서 최소 이 수 이상의 슬라이드가 와야 유효한 결과로 인정
MIN_SLIDE_COUNT = 5


SLIDE_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "slides": {
            "type": "array",
            "description": "슬라이드 목록",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string", "description": "슬라이드 제목 (15자 이내)"},
                    "body": {"type": "string", "description": "핵심 설명 (50자 이내)"},
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "핵심 포인트 3~5개 (각 25자 이내)",
                    },
                    "speaker_notes": {"type": "string", "description": "발표 노트 (100~200자)"},
                    "slide_category": {
                        "type": "string",
                        "description": "슬라이드 카테고리",
                    },
                },
                "required": ["title", "body", "bullets", "speaker_notes", "slide_category"],
            },
        },
    },
    "required": ["slides"],
}


def plan_slides(
    rfx_result: dict[str, Any],
    proposal_sections: Optional[list[dict[str, str]]] = None,
    target_slide_count: int = 20,
    duration_min: int = 30,
    knowledge_texts: Optional[list[str]] = None,
    rfp_context: str = "",
    company_context: str = "",
    api_key: Optional[str] = None,
    profile_md: str = "",
) -> list[SlideContent]:
    """슬라이드 구성 계획.

    LLM이 RFP를 분석하여 슬라이드별 콘텐츠를 생성.
    LLM 실패 시 기존 템플릿 기반 구조 fallback.

    Args:
        rfx_result: RFP 분석 결과
        proposal_sections: 제안서 섹션 [{"name": ..., "text": ...}]
        target_slide_count: 목표 슬라이드 수 (15~30)
        duration_min: 발표 시간(분)
        knowledge_texts: Layer 1 지식 규칙 (optional)
        rfp_context: build_rfp_context() 결과 (optional, 없으면 내부 생성)
        company_context: Layer 2 회사 맞춤 컨텍스트 (optional)
        api_key: OpenAI API key (optional)
        profile_md: 회사 제안서 프로필 (문체/전략/강점 DNA).

    Returns:
        슬라이드 목록
    """
    target_slide_count = max(15, min(30, target_slide_count))
    total_duration_sec = duration_min * 60

    # LLM-based slide planning (falls back to template on failure)
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    llm_slides = _plan_slides_llm(
        rfx_result, proposal_sections, target_slide_count,
        duration_min, knowledge_texts, rfp_context, resolved_key,
        company_context=company_context,
        profile_md=profile_md,
    )
    if llm_slides:
        # Assign duration to LLM-generated slides
        avg_sec = total_duration_sec // max(1, len(llm_slides))
        for s in llm_slides:
            s.duration_sec = avg_sec
        # Distribute extra time to content slides
        actual_total = len(llm_slides) * avg_sec
        if actual_total < total_duration_sec:
            content_slides = [s for s in llm_slides if s.slide_type == SlideType.CONTENT]
            if content_slides:
                extra_per = (total_duration_sec - actual_total) // len(content_slides)
                for s in content_slides:
                    s.duration_sec += extra_per
        return llm_slides

    # Fallback: template-based slide structure (only on LLM runtime failure)
    return _plan_slides_template(rfx_result, proposal_sections, target_slide_count, total_duration_sec)


def _plan_slides_llm(
    rfx_result: dict[str, Any],
    proposal_sections: Optional[list[dict[str, str]]],
    target_slide_count: int,
    duration_min: int,
    knowledge_texts: Optional[list[str]],
    rfp_context: str,
    api_key: str,
    company_context: str = "",
    profile_md: str = "",
) -> list[SlideContent]:
    """LLM으로 슬라이드 콘텐츠 생성 (6계층 프롬프트: Layer1 + Layer2 회사 + Profile + 템플릿 + RFP + 지시)."""
    import openai

    client = openai.OpenAI(api_key=api_key, timeout=LLM_DEFAULT_TIMEOUT)

    # Build 6-layer prompt
    parts: list[str] = []

    # Layer 1 — universal knowledge
    if knowledge_texts:
        rules = "\n".join(f"- {t}" for t in knowledge_texts[:8])
        parts.append(f"## PT 발표자료 작성 핵심 규칙 (공공조달 지식):\n{rules}")

    # Layer 1.5 — company context (유사실적, 투입인력, 강점)
    if company_context:
        parts.append(f"## 제안사 역량 정보:\n{company_context[:2000]}")

    # Layer 1.7 — company profile (문체, 강점 패턴, 전략 — 반드시 준수)
    if profile_md:
        parts.append(f"## 이 회사의 제안서 프로필 (반드시 준수):\n{profile_md}")

    # Layer 2 — slide structure template
    def _slide_label(s: dict) -> str:
        if s.get("fixed"):
            return "고정"
        ratio = s.get("ratio", 0)
        return f"비중 {ratio:.0%}"

    structure_str = "\n".join(
        f"- {s['name']} ({s['type'].value}): {_slide_label(s)}"
        for s in DEFAULT_SLIDE_STRUCTURE
    )
    parts.append(f"## 공공조달 PT 표준 구성:\n{structure_str}")

    # Layer 3 — RFP context (build_rfp_context() or inline fallback)
    context_section = f"## 사업 정보:\n{rfp_context}" if rfp_context else ""
    if not context_section:
        context_section = (
            f"## 사업 정보:\n"
            f"사업명: {rfx_result.get('title', '')}\n"
            f"발주기관: {rfx_result.get('issuing_org', '')}\n"
            f"사업비: {rfx_result.get('budget', '')}\n"
            f"사업기간: {rfx_result.get('project_period', '')}"
        )

    # Append requirements
    requirements_str = ""
    for req in rfx_result.get("requirements", []):
        desc = req.get("description", "") if isinstance(req, dict) else str(req)
        if desc:
            requirements_str += f"- {desc}\n"
    if requirements_str:
        context_section += f"\n\n핵심 요구사항:\n{requirements_str}"

    # Append proposal section summaries if available
    if proposal_sections:
        sec_str = ""
        for sec in proposal_sections[:5]:
            sec_str += f"\n[{sec.get('name', '')}] {sec.get('text', '')[:200]}\n"
        context_section += f"\n\n제안서 섹션 요약:{sec_str}"

    parts.append(context_section)

    # Layer 4 — generation instructions
    parts.append(
        f"## 작성 지시:\n"
        f"위 사업 정보를 기반으로 기술평가 PT 발표자료의 슬라이드 {target_slide_count}장 콘텐츠를 생성하세요.\n"
        f"발표 시간: {duration_min}분\n\n"
        f"규칙:\n"
        f"1. 각 슬라이드에 제목/본문/불렛포인트/발표노트를 모두 채울 것\n"
        f"2. slide_category: cover/toc/divider/bullet/content/timeline/team/table/qna/closing 중 택일\n"
        f"3. 불렛 포인트는 이 사업에 구체적인 내용 (범용적 문구 금지)\n"
        f"4. 발표 노트에 전환 멘트와 강조점 포함\n"
        f"5. 평가 배점이 높은 항목에 더 많은 슬라이드 배분"
    )

    prompt = "\n\n".join(parts)

    system_prompt = (
        "당신은 대한민국 공공조달 기술평가 PT 발표자료 작성 전문가입니다. "
        "평가위원이 높은 점수를 줄 수 있도록 구체적이고 전문적인 슬라이드를 구성합니다."
    )

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=6000,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "slide_plan",
                    "strict": True,
                    "schema": SLIDE_PLAN_SCHEMA,
                },
            },
        )

    try:
        resp = call_with_retry(_call)
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            logger.warning("Slide planning truncated, using template fallback")
            return []
        raw = choice.message.content or "{}"
        result = json.loads(raw)
        items = result.get("slides", [])
    except Exception as exc:
        logger.warning("LLM slide planning failed: %s", exc)
        return []

    if not isinstance(items, list) or len(items) < MIN_SLIDE_COUNT:
        return []

    # Map category string to SlideType
    category_map = {
        "cover": SlideType.COVER,
        "toc": SlideType.TOC,
        "bullet": SlideType.BULLET,
        "content": SlideType.CONTENT,
        "timeline": SlideType.TIMELINE,
        "team": SlideType.TEAM,
        "table": SlideType.TABLE,
        "qna": SlideType.QNA,
        "closing": SlideType.CLOSING,
        "divider": SlideType.DIVIDER,
    }

    slides: list[SlideContent] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cat = item.get("slide_category", "content")
        slides.append(SlideContent(
            slide_type=category_map.get(cat, SlideType.CONTENT),
            title=item.get("title", ""),
            body=item.get("body", ""),
            bullets=item.get("bullets", []),
            speaker_notes=item.get("speaker_notes", ""),
        ))

    return slides


def _plan_slides_template(
    rfx_result: dict[str, Any],
    proposal_sections: Optional[list[dict[str, str]]],
    target_slide_count: int,
    total_duration_sec: int,
) -> list[SlideContent]:
    """템플릿 기반 슬라이드 구성 (LLM 실패 시 fallback)."""
    fixed_count = sum(s.get("count", 0) for s in DEFAULT_SLIDE_STRUCTURE if s.get("fixed"))
    variable_budget = target_slide_count - fixed_count

    variable_slides = [s for s in DEFAULT_SLIDE_STRUCTURE if not s.get("fixed")]
    total_ratio = sum(s.get("ratio", 0) for s in variable_slides)

    slides: list[SlideContent] = []
    avg_sec_per_slide = total_duration_sec // max(1, target_slide_count)

    for slide_def in DEFAULT_SLIDE_STRUCTURE:
        if slide_def.get("fixed"):
            count = slide_def["count"]
        else:
            ratio = slide_def.get("ratio", 0.1)
            count = max(1, round(variable_budget * ratio / max(total_ratio, 0.01)))

        for i in range(count):
            title = slide_def["name"]
            if count > 1:
                title = f"{slide_def['name']} ({i + 1})"

            body = ""
            if proposal_sections:
                for sec in proposal_sections:
                    sec_name = sec.get("name", "")
                    if slide_def["name"] in sec_name or sec_name in slide_def["name"]:
                        body = sec.get("text", "")[:500]
                        break

            slides.append(SlideContent(
                slide_type=slide_def["type"],
                title=title,
                body=body,
                duration_sec=avg_sec_per_slide,
            ))

    # Distribute remaining time
    actual_total = len(slides) * avg_sec_per_slide
    if actual_total < total_duration_sec and slides:
        content_slides = [s for s in slides if s.slide_type == SlideType.CONTENT]
        if content_slides:
            extra_per = (total_duration_sec - actual_total) // len(content_slides)
            for s in content_slides:
                s.duration_sec += extra_per

    return slides


QNA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "qna_pairs": {
            "type": "array",
            "description": "예상질문 + 모범답변 목록",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "question": {"type": "string", "description": "예상 질문"},
                    "answer": {"type": "string", "description": "모범 답변 (200~300자)"},
                    "category": {"type": "string", "description": "카테고리 (기술/관리/비용/인력/보안)"},
                },
                "required": ["question", "answer", "category"],
            },
        },
    },
    "required": ["qna_pairs"],
}


def generate_qna_pairs(
    rfx_result: dict[str, Any],
    proposal_sections: Optional[list[dict[str, str]]] = None,
    count: int = 10,
    api_key: Optional[str] = None,
    knowledge_texts: Optional[list[str]] = None,
    rfp_context: str = "",
    company_context: str = "",
) -> list[QnaPair]:
    """공공조달 기술평가 위원 관점의 예상질문 + 모범답변 생성.

    5계층 프롬프트: Layer 1 지식 → 회사 역량 → RFP 컨텍스트 → 제안서 요약 → 생성 지시
    """
    import openai

    client = openai.OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    parts: list[str] = []

    # Layer 1 — universal knowledge
    if knowledge_texts:
        rules = "\n".join(f"- {t}" for t in knowledge_texts[:5])
        parts.append(f"## 기술평가 예상질문 패턴 (공공조달 지식):\n{rules}")

    # Layer 1.5 — company context (평가위원이 회사 역량 관련 질문할 때 활용)
    if company_context:
        parts.append(f"## 제안사 역량 정보 (답변에 활용):\n{company_context[:1500]}")

    # Layer 2/3 — RFP context (build_rfp_context() or inline fallback)
    context_section = f"## 사업 정보:\n{rfp_context}" if rfp_context else ""
    if not context_section:
        context_section = (
            f"## 사업 정보:\n"
            f"사업명: {rfx_result.get('title', '')}\n"
            f"발주기관: {rfx_result.get('issuing_org', '')}\n"
            f"사업비: {rfx_result.get('budget', '')}\n"
            f"사업기간: {rfx_result.get('project_period', '')}"
        )

    # Append requirements
    requirements_str = ""
    for req in rfx_result.get("requirements", []):
        desc = req.get("description", "") if isinstance(req, dict) else str(req)
        if desc:
            requirements_str += f"- {desc}\n"
    if requirements_str:
        context_section += f"\n\n핵심 요구사항:\n{requirements_str}"

    # Append proposal section summaries
    if proposal_sections:
        sections_str = ""
        for sec in proposal_sections[:5]:
            sections_str += f"\n[{sec.get('name', '')}]\n{sec.get('text', '')[:300]}\n"
        context_section += f"\n제안 내용 요약:{sections_str}"

    parts.append(context_section)

    # Layer 4 — generation instructions
    parts.append(
        f"## 작성 지시:\n"
        f"위 사업에 대해 기술평가 PT 후 예상되는 질문 {count}개와 모범답변을 생성하세요.\n\n"
        f"규칙:\n"
        f"1. 실제 공공조달 기술평가 위원이 묻는 유형의 질문\n"
        f"2. 카테고리별 균형: 기술 50%, 관리 20%, 비용/인력/보안 30%\n"
        f"3. 모범답변에 구체적 수치, 방법론, 사례 포함\n"
        f"4. 이 사업의 핵심 쟁점에 집중 (범용 질문 금지)"
    )

    prompt = "\n\n".join(parts)

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 공공조달 기술평가 위원 경험 20년의 전문가입니다. 실제 평가에서 묻는 질문을 생성합니다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=4000,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "qna_generation",
                    "strict": True,
                    "schema": QNA_SCHEMA,
                },
            },
        )

    try:
        resp = call_with_retry(_call)
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            logger.warning("QnA generation truncated")
            return []
        raw = choice.message.content or "{}"
        result = json.loads(raw)
        items = result.get("qna_pairs", [])
    except Exception as exc:
        logger.warning("QnA generation failed: %s", exc)
        return []

    if not isinstance(items, list):
        return []

    pairs: list[QnaPair] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        pairs.append(QnaPair(
            question=item.get("question", ""),
            answer=item.get("answer", ""),
            category=item.get("category", ""),
        ))

    return pairs[:count]
