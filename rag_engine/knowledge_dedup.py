"""Knowledge Deduplicator — Pass 2 conflict resolution.

Takes Pass 1 extracted units, deduplicates against existing DB,
and resolves conflicts via 3-step pipeline:
AGREE (merge), CONDITIONAL (split with condition), CONFLICT (weighted vote).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from knowledge_models import KnowledgeUnit

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """두 지식 단위가 모순인지 판별하세요:

Rule A: "{rule_a}" (소스: {source_a})
Rule B: "{rule_b}" (소스: {source_b})

다음 중 하나로 답하세요:
1. AGREE — 같은 내용을 다르게 표현 (→ 병합)
2. CONDITIONAL — 둘 다 맞지만 적용 조건이 다름 (→ 각각의 condition 설명)
3. CONFLICT — 같은 상황에서 다른 결론 (→ 어느 쪽이 더 정확한지 근거 제시)

JSON 형식으로만 답하세요:
{{"verdict": "AGREE|CONDITIONAL|CONFLICT", "condition_a": "", "condition_b": "", "winner": "A|B", "reasoning": ""}}"""


@dataclass
class ConflictResolution:
    rule_a_id: str
    rule_b_id: str
    verdict: str          # AGREE | CONDITIONAL | CONFLICT
    condition_a: str
    condition_b: str
    winner: str
    reasoning: str


def _call_llm_for_classification(
    rule_a: str, source_a: str, rule_b: str, source_b: str,
    api_key: Optional[str] = None,
) -> str:
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    prompt = CLASSIFICATION_PROMPT.format(
        rule_a=rule_a, source_a=source_a,
        rule_b=rule_b, source_b=source_b,
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=500,
    )
    return resp.choices[0].message.content or "{}"


def classify_relationship(
    unit_a: KnowledgeUnit, unit_b: KnowledgeUnit,
) -> ConflictResolution:
    """Classify the relationship between two similar knowledge units."""
    raw = _call_llm_for_classification(
        unit_a.rule, unit_a.source_type.value,
        unit_b.rule, unit_b.source_type.value,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse conflict classification response")
        data = {"verdict": "AGREE", "reasoning": "parse_error_fallback"}

    return ConflictResolution(
        rule_a_id=f"{unit_a.category.value}:{unit_a.rule[:50]}",
        rule_b_id=f"{unit_b.category.value}:{unit_b.rule[:50]}",
        verdict=data.get("verdict", "AGREE"),
        condition_a=data.get("condition_a", ""),
        condition_b=data.get("condition_b", ""),
        winner=data.get("winner", ""),
        reasoning=data.get("reasoning", ""),
    )


def resolve_and_merge(
    unit_a: KnowledgeUnit, unit_b: KnowledgeUnit,
) -> list[KnowledgeUnit]:
    """Resolve relationship and return merged/split/marked units."""
    resolution = classify_relationship(unit_a, unit_b)

    if resolution.verdict == "AGREE":
        unit_a.source_count += 1
        return [unit_a]

    elif resolution.verdict == "CONDITIONAL":
        unit_a.condition = resolution.condition_a
        unit_b.condition = resolution.condition_b
        return [unit_a, unit_b]

    elif resolution.verdict == "CONFLICT":
        if resolution.winner == "B":
            winner, loser = unit_b, unit_a
        else:
            winner, loser = unit_a, unit_b
        winner.has_conflict_flag = True
        loser.deprecated_by = winner.rule[:50]
        loser.raw_confidence = round(loser.raw_confidence * 0.3, 3)
        return [winner, loser]

    # Fallback: treat as agree
    unit_a.source_count += 1
    return [unit_a]
