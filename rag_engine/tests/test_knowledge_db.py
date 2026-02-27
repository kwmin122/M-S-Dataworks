from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from knowledge_models import KnowledgeUnit, KnowledgeCategory, SourceType
from knowledge_db import KnowledgeDB


@pytest.fixture
def tmp_db(tmp_path):
    db = KnowledgeDB(persist_directory=str(tmp_path / "test_kb"))
    yield db


def test_add_and_search(tmp_db):
    unit = KnowledgeUnit(
        category=KnowledgeCategory.WRITING,
        subcategory="page_layout",
        rule="한 페이지에 핵심 메시지는 1개만 담는다",
        explanation="평가위원은 시간이 없어서 캡션과 강조 문구만 본다.",
        source_type=SourceType.YOUTUBE,
        raw_confidence=0.75,
        source_count=1,
        source_date="2025-09",
    )
    tmp_db.add(unit)
    results = tmp_db.search("페이지 레이아웃 핵심 메시지", top_k=3)
    assert len(results) >= 1
    assert results[0].rule == unit.rule


def test_search_by_category(tmp_db):
    tmp_db.add(KnowledgeUnit(
        category=KnowledgeCategory.PITFALL,
        subcategory="blind_eval",
        rule="블라인드 평가에서 회사명 노출은 즉시 탈락",
        explanation="회사명, 로고 등 식별 정보가 제안서에 포함되면 감점 또는 탈락.",
        source_type=SourceType.OFFICIAL_GUIDE,
        raw_confidence=0.85,
    ))
    tmp_db.add(KnowledgeUnit(
        category=KnowledgeCategory.WRITING,
        subcategory="tone",
        rule="격식체 사용",
        explanation="공공 제안서는 격식체가 기본.",
        source_type=SourceType.BLOG,
        raw_confidence=0.35,
    ))
    pitfalls = tmp_db.search("감점 요소", top_k=5, category=KnowledgeCategory.PITFALL)
    assert all(r.category == KnowledgeCategory.PITFALL for r in pitfalls)


def test_count(tmp_db):
    assert tmp_db.count() == 0
    tmp_db.add(KnowledgeUnit(
        category=KnowledgeCategory.STRUCTURE,
        subcategory="outline",
        rule="test rule",
        explanation="test explanation",
        source_type=SourceType.BLOG,
    ))
    assert tmp_db.count() == 1


def test_add_batch(tmp_db):
    units = [
        KnowledgeUnit(
            category=KnowledgeCategory.EVALUATION,
            subcategory=f"item_{i}",
            rule=f"평가 규칙 {i}",
            explanation=f"설명 {i}",
            source_type=SourceType.OFFICIAL_GUIDE,
        )
        for i in range(5)
    ]
    tmp_db.add_batch(units)
    assert tmp_db.count() == 5
