from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from knowledge_models import ProposalOutline, ProposalSection
from proposal_planner import build_proposal_outline


def _make_rfx_result():
    return {
        "title": "XX기관 정보시스템 구축 사업",
        "issuing_org": "XX기관",
        "budget": "5억원",
        "project_period": "12개월",
        "evaluation_criteria": [
            {"category": "사업 이해도", "max_score": 15, "description": "사업 배경 및 목적 이해"},
            {"category": "기술성", "max_score": 40, "description": "시스템 아키텍처, 구현방안"},
            {"category": "수행관리", "max_score": 15, "description": "일정관리, 품질관리, 리스크관리"},
        ],
        "requirements": [
            {"category": "기술요건", "description": "클라우드 기반 웹 시스템 구축"},
        ],
    }


def test_build_outline_from_evaluation_criteria():
    rfx = _make_rfx_result()
    outline = build_proposal_outline(rfx, total_pages=50)
    assert isinstance(outline, ProposalOutline)
    assert outline.title == rfx["title"]
    assert len(outline.sections) >= 3
    tech_section = next(s for s in outline.sections if "기술" in s.name)
    understand_section = next(s for s in outline.sections if "이해" in s.name)
    assert tech_section.weight > understand_section.weight


def test_build_outline_includes_standard_sections():
    rfx = _make_rfx_result()
    outline = build_proposal_outline(rfx, total_pages=50)
    section_names = [s.name for s in outline.sections]
    assert any("요약" in n or "개요" in n for n in section_names)


def test_build_outline_empty_eval_criteria():
    rfx = {"title": "테스트", "issuing_org": "테스트기관", "evaluation_criteria": [], "requirements": []}
    outline = build_proposal_outline(rfx, total_pages=30)
    assert len(outline.sections) >= 3


def test_coarse_criteria_falls_back_to_defaults():
    """When eval_criteria are just scoring buckets (기술평가/가격평가),
    planner should use DEFAULT_SECTIONS instead of creating 2-3 useless sections."""
    rfx = {
        "title": "CCTV발주사업",
        "issuing_org": "XX기관",
        "evaluation_criteria": [
            {"category": "제안 개요", "max_score": 10, "description": ""},
            {"category": "기술평가", "max_score": 60, "description": ""},
            {"category": "가격평가", "max_score": 30, "description": ""},
        ],
        "requirements": [],
    }
    outline = build_proposal_outline(rfx, total_pages=50)
    section_names = [s.name for s in outline.sections]
    # Should NOT have "기술평가" or "가격평가" as section names
    assert "기술평가" not in section_names
    assert "가격평가" not in section_names
    # Should have proper sections from DEFAULT_SECTIONS
    assert len(outline.sections) >= 5
    assert any("접근" in n or "기술" in n for n in section_names)
    assert any("수행" in n or "관리" in n for n in section_names)


def test_item_based_criteria_produces_proper_sections():
    """When eval_criteria have actual item names (from _build_rfx_dict),
    these should become proper section names."""
    rfx = {
        "title": "정보시스템 구축",
        "issuing_org": "교육청",
        "evaluation_criteria": [
            {"category": "사업 이해도", "parent_category": "기술평가", "max_score": 15, "description": "사업 배경 이해"},
            {"category": "기술적 접근방안", "parent_category": "기술평가", "max_score": 30, "description": "아키텍처 설계"},
            {"category": "수행관리 방안", "parent_category": "기술평가", "max_score": 15, "description": "일정 및 품질"},
            {"category": "투입인력 및 조직", "parent_category": "기술평가", "max_score": 10, "description": "PM/PL 구성"},
            {"category": "유사 수행실적", "parent_category": "기술평가", "max_score": 10, "description": "관련 경험"},
        ],
        "requirements": [],
    }
    outline = build_proposal_outline(rfx, total_pages=50)
    section_names = [s.name for s in outline.sections]
    assert "사업 이해도" in section_names
    assert "기술적 접근방안" in section_names
    assert len(outline.sections) >= 5
