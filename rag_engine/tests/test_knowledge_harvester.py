from __future__ import annotations
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch
from knowledge_harvester import extract_knowledge_units
from knowledge_models import KnowledgeCategory, SourceType


SAMPLE_TRANSCRIPT = """
제안서를 쓸 때 가장 중요한 건 평가위원의 시선입니다.
평가위원은 제안서를 처음부터 끝까지 안 읽어요.
캡션, 강조 문구, 그래픽만 봅니다.
그래서 한 페이지에 핵심 메시지는 딱 하나만 넣어야 합니다.
그리고 블라인드 평가에서 회사명이 노출되면 바로 감점이에요.
꼭 확인하세요.
"""

MOCK_LLM_RESPONSE = json.dumps([
    {
        "category": "writing",
        "subcategory": "page_layout",
        "rule": "한 페이지에 핵심 메시지는 1개만 담는다",
        "explanation": "평가위원은 시간이 없어서 캡션과 강조 문구만 본다.",
        "example_good": "",
        "example_bad": "",
        "confidence": 0.75,
    },
    {
        "category": "pitfall",
        "subcategory": "blind_evaluation",
        "rule": "블라인드 평가에서 회사명 노출 시 감점",
        "explanation": "회사명, 로고 등 식별 가능 정보가 포함되면 감점 또는 탈락 처리.",
        "example_good": "",
        "example_bad": "",
        "confidence": 0.85,
    },
])


def test_extract_knowledge_units_from_text():
    with patch("knowledge_harvester._call_llm_for_extraction") as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE
        units = extract_knowledge_units(
            text=SAMPLE_TRANSCRIPT,
            source_type=SourceType.YOUTUBE,
            source_id="test_video_001",
            source_date="2025-09",
        )
    assert len(units) == 2
    assert units[0].category == KnowledgeCategory.WRITING
    assert units[1].category == KnowledgeCategory.PITFALL
    assert units[0].source_type == SourceType.YOUTUBE
    assert units[0].source_id == "test_video_001"


def test_extract_handles_empty_response():
    with patch("knowledge_harvester._call_llm_for_extraction") as mock_llm:
        mock_llm.return_value = "[]"
        units = extract_knowledge_units(
            text="짧은 텍스트",
            source_type=SourceType.BLOG,
        )
    assert units == []


def test_extract_handles_invalid_json():
    with patch("knowledge_harvester._call_llm_for_extraction") as mock_llm:
        mock_llm.return_value = "not valid json"
        units = extract_knowledge_units(
            text="어떤 텍스트",
            source_type=SourceType.BLOG,
        )
    assert units == []
