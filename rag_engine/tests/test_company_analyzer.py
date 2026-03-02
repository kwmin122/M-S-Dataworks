from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from company_analyzer import analyze_company_style, StyleProfile


def test_analyze_empty_documents():
    result = analyze_company_style([])
    assert isinstance(result, StyleProfile)
    assert result.avg_sentence_length == 0.0


def test_detect_formal_tone():
    doc = """
    본 사업은 클라우드 전환을 위한 프로젝트이다.
    시스템 아키텍처는 3-tier로 구성함.
    데이터베이스는 PostgreSQL을 사용함.
    보안 체계를 강화함.
    """
    result = analyze_company_style([doc])
    assert result.tone == "격식체"


def test_detect_polite_tone():
    doc = """
    본 사업은 클라우드 전환을 위한 프로젝트입니다.
    시스템 아키텍처는 3-tier로 구성합니다.
    데이터베이스는 PostgreSQL을 사용합니다.
    보안 체계를 강화합니다.
    """
    result = analyze_company_style([doc])
    assert result.tone == "경어체"


def test_extract_strength_keywords():
    doc = "클라우드 마이그레이션 클라우드 전환 클라우드 인프라 구축 사업"
    result = analyze_company_style([doc])
    assert "클라우드" in result.strength_keywords


def test_avg_sentence_length():
    doc = "짧은 문장이다. 이것도 짧은 문장이다. 조금 더 긴 문장을 작성해 보았다."
    result = analyze_company_style([doc])
    assert result.avg_sentence_length > 0
