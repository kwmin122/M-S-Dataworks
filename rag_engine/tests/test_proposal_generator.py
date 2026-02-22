import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from proposal_generator import extract_template_sections, fill_template_sections


def test_extract_sections_empty():
    """빈 텍스트 → 빈 섹션 dict"""
    result = extract_template_sections("")
    assert isinstance(result, dict)


def test_extract_sections_finds_placeholders():
    """{{섹션명}} 플레이스홀더 파싱"""
    text = "{{사업개요}}\n내용\n{{수행전략}}"
    result = extract_template_sections(text)
    assert "사업개요" in result
    assert "수행전략" in result


def test_fill_sections_returns_dict():
    sections = {"사업개요": "{{사업개요}}", "수행전략": "{{수행전략}}"}
    notice_text = "경기도청 CCTV 교체사업 입찰공고"
    result = fill_template_sections(sections, notice_text, company_info={"name": "테스트"})
    assert isinstance(result, dict)
    assert "사업개요" in result
