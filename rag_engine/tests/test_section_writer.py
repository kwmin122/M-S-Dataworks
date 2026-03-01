from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch
from knowledge_models import ProposalSection, KnowledgeUnit, KnowledgeCategory, SourceType
from section_writer import write_section, _assemble_prompt


def test_assemble_prompt_includes_layer1_knowledge():
    section = ProposalSection(
        name="기술적 접근방안",
        evaluation_item="시스템 아키텍처 및 구현방안",
        max_score=40,
        weight=0.4,
    )
    knowledge = [
        KnowledgeUnit(
            category=KnowledgeCategory.WRITING,
            subcategory="page_layout",
            rule="한 페이지에 핵심 메시지는 1개만 담는다",
            explanation="평가위원은 시간 부족.",
            source_type=SourceType.YOUTUBE,
            raw_confidence=0.75,
        ),
    ]
    rfp_context = "클라우드 기반 웹 시스템 구축 사업"
    prompt = _assemble_prompt(section, knowledge, rfp_context)
    assert "기술적 접근방안" in prompt
    assert "핵심 메시지는 1개만" in prompt
    assert "클라우드" in prompt


def test_assemble_prompt_works_without_knowledge():
    section = ProposalSection(
        name="제안 개요",
        evaluation_item="Executive Summary",
        max_score=0,
        weight=0.05,
    )
    prompt = _assemble_prompt(section, [], "테스트 RFP")
    assert "제안 개요" in prompt


def test_write_section_returns_text():
    section = ProposalSection(
        name="사업 이해도",
        evaluation_item="사업 배경 및 목적 이해",
        max_score=15,
        weight=0.15,
    )
    with patch("section_writer._call_llm_for_section") as mock_llm:
        mock_llm.return_value = "## 사업 이해도\n\n본 사업은 XX기관의 정보시스템 현대화를 위한..."
        result = write_section(
            section=section,
            rfp_context="XX기관 정보시스템 구축",
            knowledge=[],
        )
    assert "사업 이해도" in result
    assert len(result) > 20


def test_write_section_with_profile_md():
    """profile_md가 프롬프트에 주입되는지 확인."""
    from unittest.mock import patch
    from knowledge_models import ProposalSection

    section = ProposalSection(
        name="기술 방안",
        evaluation_item="기술이해도",
        max_score=20,
        weight=0.25,
    )
    profile_md = "## 문체\n- 어미: ~합니다 (경어체)\n- 핵심 키워드: 클라우드, 보안"

    with patch("section_writer._call_llm_for_section") as mock_llm:
        mock_llm.return_value = "## 기술 방안\n\n내용입니다."
        from section_writer import write_section
        result = write_section(
            section=section,
            rfp_context="사업명: 테스트",
            knowledge=[],
            company_context="",
            profile_md=profile_md,
        )
        # profile_md가 프롬프트에 포함되었는지 확인
        called_prompt = mock_llm.call_args[0][0]
        assert "제안서 프로필" in called_prompt
        assert "경어체" in called_prompt
        assert "클라우드" in called_prompt


def test_write_section_without_profile_md():
    """profile_md 없이도 기존과 동일하게 동작."""
    from unittest.mock import patch
    from knowledge_models import ProposalSection

    section = ProposalSection(
        name="사업 이해",
        evaluation_item="사업이해도",
        max_score=15,
        weight=0.15,
    )

    with patch("section_writer._call_llm_for_section") as mock_llm:
        mock_llm.return_value = "## 사업 이해\n\n내용입니다."
        from section_writer import write_section
        result = write_section(
            section=section,
            rfp_context="사업명: 테스트",
            knowledge=[],
        )
        assert result == "## 사업 이해\n\n내용입니다."
        # profile 관련 텍스트 없음
        called_prompt = mock_llm.call_args[0][0]
        assert "제안서 프로필" not in called_prompt
