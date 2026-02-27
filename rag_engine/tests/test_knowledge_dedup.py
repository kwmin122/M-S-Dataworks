from __future__ import annotations
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch
from knowledge_dedup import classify_relationship, resolve_and_merge, ConflictResolution
from knowledge_models import KnowledgeUnit, KnowledgeCategory, SourceType


def _make_unit(rule, category=KnowledgeCategory.WRITING, confidence=0.55, source=SourceType.YOUTUBE):
    return KnowledgeUnit(
        category=category,
        subcategory="test",
        rule=rule,
        explanation=f"설명: {rule}",
        source_type=source,
        raw_confidence=confidence,
        source_count=1,
    )


MOCK_AGREE = json.dumps({
    "verdict": "AGREE",
    "condition_a": "",
    "condition_b": "",
    "winner": "",
    "reasoning": "같은 내용을 다르게 표현",
})

MOCK_CONDITIONAL = json.dumps({
    "verdict": "CONDITIONAL",
    "condition_a": "적격심사 방식 입찰일 때",
    "condition_b": "기술평가 방식 입찰일 때",
    "winner": "",
    "reasoning": "입찰 방식에 따라 적용이 다름",
})

MOCK_CONFLICT = json.dumps({
    "verdict": "CONFLICT",
    "condition_a": "",
    "condition_b": "",
    "winner": "B",
    "reasoning": "공식 가이드가 더 정확함",
})


def test_classify_agree():
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_AGREE
        result = classify_relationship(
            _make_unit("한 페이지에 핵심 메시지 1개"),
            _make_unit("페이지당 하나의 메시지만"),
        )
    assert result.verdict == "AGREE"


def test_classify_conditional():
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_CONDITIONAL
        result = classify_relationship(
            _make_unit("실적기술서는 최대한 많이 넣어라"),
            _make_unit("실적기술서는 상위 5건만 선별"),
        )
    assert result.verdict == "CONDITIONAL"
    assert "적격심사" in result.condition_a
    assert "기술평가" in result.condition_b


def test_classify_conflict():
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_CONFLICT
        result = classify_relationship(
            _make_unit("표지에 사업명만 적는다"),
            _make_unit("표지에 사업명+제안사명+제출일자"),
        )
    assert result.verdict == "CONFLICT"
    assert result.winner == "B"


def test_resolve_agree_merges():
    unit_a = _make_unit("핵심 메시지 1개", confidence=0.55)
    unit_b = _make_unit("페이지당 메시지 1개", confidence=0.35)
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_AGREE
        merged = resolve_and_merge(unit_a, unit_b)
    assert len(merged) == 1
    assert merged[0].source_count == 2


def test_resolve_conditional_splits():
    unit_a = _make_unit("실적 많이 넣어라", confidence=0.55)
    unit_b = _make_unit("실적 5건만", confidence=0.85, source=SourceType.OFFICIAL_GUIDE)
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_CONDITIONAL
        result = resolve_and_merge(unit_a, unit_b)
    assert len(result) == 2
    assert result[0].condition != ""
    assert result[1].condition != ""


def test_resolve_conflict_marks_winner():
    unit_a = _make_unit("표지에 사업명만", confidence=0.35, source=SourceType.BLOG)
    unit_b = _make_unit("표지에 사업명+제안사명+일자", confidence=0.85, source=SourceType.OFFICIAL_GUIDE)
    with patch("knowledge_dedup._call_llm_for_classification") as mock_llm:
        mock_llm.return_value = MOCK_CONFLICT
        result = resolve_and_merge(unit_a, unit_b)
    winner = [u for u in result if u.has_conflict_flag]
    loser = [u for u in result if u.deprecated_by]
    assert len(winner) == 1
    assert len(loser) == 1
    assert loser[0].raw_confidence < 0.35
