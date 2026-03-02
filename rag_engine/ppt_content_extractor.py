"""PPT Content Extractor — 제안서 섹션에서 슬라이드 콘텐츠 추출.

제안서 섹션 텍스트에서 핵심 메시지를 추출하여 슬라이드용 콘텐츠 생성.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT
from phase2_models import SlideType, SlideContent

logger = logging.getLogger(__name__)


SLIDE_CONTENT_SCHEMA: dict[str, Any] = {
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
    },
    "required": ["title", "body", "bullets", "speaker_notes"],
}


def extract_slide_content(
    section_name: str,
    section_text: str,
    slide_type: SlideType,
    api_key: Optional[str] = None,
    knowledge_texts: Optional[list[str]] = None,
    rfp_context: str = "",
    company_context: str = "",
) -> SlideContent:
    """제안서 섹션에서 슬라이드용 핵심 콘텐츠 추출 (5계층 프롬프트)."""
    import openai

    client = openai.OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    # Build 4-layer prompt
    parts: list[str] = []

    # Layer 1 — universal knowledge
    if knowledge_texts:
        rules = "\n".join(f"- {t}" for t in knowledge_texts[:5])
        parts.append(f"## PT 슬라이드 작성 규칙:\n{rules}")

    # Layer 1.5 — company context
    if company_context:
        parts.append(f"## 제안사 역량 정보:\n{company_context[:1000]}")

    # Layer 2 — RFP context
    if rfp_context:
        parts.append(f"## 사업 정보:\n{rfp_context[:1000]}")

    # Layer 3 — section content
    parts.append(f"## 제안서 섹션: {section_name}\n{section_text[:2000]}")

    # Layer 4 — generation instructions
    parts.append(
        "## 작성 지시:\n"
        "위 섹션에서 슬라이드 1장에 들어갈 핵심 콘텐츠를 추출하세요.\n\n"
        "규칙:\n"
        "1. bullets는 3~5개, 각 25자 이내, 이 사업에 구체적인 내용\n"
        "2. speaker_notes에 핵심 강조점과 전환 멘트 포함\n"
        "3. 범용적 문구가 아닌 이 사업 특화 내용"
    )

    prompt = "\n\n".join(parts)

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "공공조달 기술평가 PT 콘텐츠 전문가. 평가위원에게 어필하는 슬라이드를 구성합니다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "slide_content",
                    "strict": True,
                    "schema": SLIDE_CONTENT_SCHEMA,
                },
            },
        )

    try:
        resp = call_with_retry(_call)
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            logger.warning("Slide content extraction truncated for %s", section_name)
            return SlideContent(
                slide_type=slide_type,
                title=section_name[:20],
                body=section_text[:100],
                speaker_notes=section_text[:200],
            )
        raw = choice.message.content or "{}"
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("Slide content extraction failed for %s: %s", section_name, exc)
        return SlideContent(
            slide_type=slide_type,
            title=section_name[:20],
            body=section_text[:100],
            speaker_notes=section_text[:200],
        )

    return SlideContent(
        slide_type=slide_type,
        title=data.get("title", section_name[:20]),
        body=data.get("body", ""),
        bullets=data.get("bullets", []),
        speaker_notes=data.get("speaker_notes", ""),
    )


def extract_key_messages(
    full_text: str,
    max_messages: int = 5,
    api_key: Optional[str] = None,
) -> list[str]:
    """전체 텍스트에서 핵심 메시지 추출."""
    import openai

    client = openai.OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    prompt = f"""아래 제안서 텍스트에서 기술평가 위원에게 어필할 핵심 메시지 {max_messages}개를 추출해주세요.
각 메시지는 한 줄(30자 이내)로 작성하세요.

[텍스트]
{full_text[:3000]}

JSON 배열로 응답: ["메시지1", "메시지2", ...]
"""

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "핵심 메시지 추출기. JSON만 응답."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )

    try:
        resp = call_with_retry(_call)
        raw = resp.choices[0].message.content or "[]"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        items = json.loads(raw)
        if isinstance(items, list):
            return [str(m) for m in items[:max_messages]]
    except Exception as exc:
        logger.warning("Key message extraction failed: %s", exc)

    return []
