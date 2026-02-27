from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from knowledge_models import (
    KnowledgeUnit,
    KnowledgeCategory,
    SourceType,
    compute_confidence,
    compute_freshness,
)


def test_knowledge_unit_creation():
    unit = KnowledgeUnit(
        category=KnowledgeCategory.WRITING,
        subcategory="page_layout",
        rule="한 페이지에 핵심 메시지는 1개만 담는다",
        explanation="평가위원은 시간이 없어서 캡션과 강조 문구만 본다.",
        example_good="[핵심] 본 사업은 클라우드 전환을 통해 운영비 30% 절감을 달성합니다.",
        example_bad="본 사업은 클라우드 전환, 보안 강화, 운영 효율화, 데이터 분석을 통해...",
        source_type=SourceType.YOUTUBE,
        source_id="video_abc123",
        raw_confidence=0.75,
    )
    assert unit.category == KnowledgeCategory.WRITING
    assert unit.is_valid()


def test_compute_confidence_cross_validation():
    # 1 source -> x1.0
    assert compute_confidence(base=0.75, source_count=1) == 0.75
    # 2 sources -> x1.2
    assert compute_confidence(base=0.75, source_count=2) == 0.90
    # 3+ sources -> x1.4 (capped at 0.95)
    assert compute_confidence(base=0.75, source_count=3) == 0.95  # 0.75*1.4=1.05 -> cap


def test_compute_confidence_source_type_base():
    assert compute_confidence(base=0.85, source_count=1) == 0.85  # official_guide
    assert compute_confidence(base=0.35, source_count=1) == 0.35  # blog


def test_compute_freshness():
    from datetime import date
    today = date(2026, 3, 1)
    assert compute_freshness(date(2026, 1, 1), today) == 1.0   # < 6 months
    assert compute_freshness(date(2025, 6, 1), today) == 0.9   # 6-12 months
    assert compute_freshness(date(2024, 6, 1), today) == 0.7   # 1-2 years
    assert compute_freshness(date(2023, 1, 1), today) == 0.5   # 2+ years


def test_compute_freshness_law_based():
    from datetime import date
    today = date(2026, 3, 1)
    # Law-based knowledge never decays until superseded
    assert compute_freshness(date(2020, 1, 1), today, is_law_based=True) == 1.0


def test_knowledge_unit_effective_score():
    unit = KnowledgeUnit(
        category=KnowledgeCategory.EVALUATION,
        subcategory="scoring",
        rule="기술성 배점 70점 중 구현방안이 30점으로 가장 높다",
        explanation="구현방안에 가장 많은 지면을 할애해야 한다.",
        source_type=SourceType.OFFICIAL_GUIDE,
        raw_confidence=0.85,
        source_count=2,
        source_date="2025-09",
    )
    # effective_score = confidence x freshness
    score = unit.effective_score()
    assert 0.0 < score <= 1.0
