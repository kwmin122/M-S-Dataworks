"""Knowledge Harvester — LLM Pass 1 extraction pipeline.

Takes raw text (YouTube transcript, blog article, official doc)
and extracts structured KnowledgeUnit objects via LLM.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from openai import OpenAI

from knowledge_models import (
    KnowledgeCategory,
    KnowledgeUnit,
    SourceType,
    SOURCE_BASE_CONFIDENCE,
)

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """당신은 공공조달 제안서 전문가입니다.
아래 텍스트에서 제안서 작성에 도움이 되는 지식을 추출하세요.

각 지식 단위를 다음 JSON 배열 형식으로 출력하세요:
[
  {
    "category": "structure|evaluation|writing|visual|strategy|compliance|pitfall",
    "subcategory": "세부 분류 (자유 문자열)",
    "rule": "한 문장으로 된 핵심 규칙",
    "explanation": "왜 이 규칙이 중요한지 2-3문장",
    "example_good": "잘 쓴 예시 (있으면, 없으면 빈 문자열)",
    "example_bad": "못 쓴 예시 (있으면, 없으면 빈 문자열)",
    "confidence": 0.0에서 1.0 사이의 확신도
  }
]

카테고리 설명:
- structure: 문서 구조, 목차, 섹션 순서
- evaluation: 평가기준, 배점, 점수 배분
- writing: 작성 기법, 문체, 표현법
- visual: 시각화, 레이아웃, 다이어그램
- strategy: 전략적 판단, 발주처 유형별 접근
- compliance: 규정, 자격요건, 법적 요구사항
- pitfall: 흔한 실수, 감점 요소, 탈락 사유

중요:
- "제안서는 잘 써야 합니다" 같은 일반론은 제외
- 구체적이고 실행 가능한 규칙만 추출
- JSON 배열만 출력하세요. 다른 텍스트 없이."""

VALID_CATEGORIES = {c.value for c in KnowledgeCategory}


def _call_llm_for_extraction(text: str, api_key: Optional[str] = None) -> str:
    """Call LLM to extract knowledge from raw text. Returns JSON string."""
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 텍스트에서 지식을 추출하세요:\n\n{text[:12000]}"},
        ],
        temperature=0.2,
        max_tokens=4000,
    )
    return resp.choices[0].message.content or "[]"


def extract_knowledge_units(
    text: str,
    source_type: SourceType,
    source_id: str = "",
    source_date: str = "",
    api_key: Optional[str] = None,
) -> list[KnowledgeUnit]:
    """Pass 1: Extract KnowledgeUnits from raw text via LLM."""
    raw = _call_llm_for_extraction(text, api_key)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM extraction response as JSON")
        return []

    if not isinstance(items, list):
        return []

    units: list[KnowledgeUnit] = []
    base_conf = SOURCE_BASE_CONFIDENCE.get(source_type, 0.5)
    for item in items:
        cat_str = item.get("category", "")
        if cat_str not in VALID_CATEGORIES:
            continue
        unit = KnowledgeUnit(
            category=KnowledgeCategory(cat_str),
            subcategory=item.get("subcategory", ""),
            rule=item.get("rule", ""),
            explanation=item.get("explanation", ""),
            example_good=item.get("example_good", ""),
            example_bad=item.get("example_bad", ""),
            source_type=source_type,
            source_id=source_id,
            source_date=source_date,
            raw_confidence=base_conf,
            source_count=1,
        )
        if unit.is_valid():
            units.append(unit)
    return units
