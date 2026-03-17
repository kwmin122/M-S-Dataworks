from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from quality_checker import check_quality, QualityIssue


def test_detect_blind_violation():
    text = "당사 키라솔루션즈는 최고의 기술력을 보유하고 있습니다."
    issues = check_quality(text, company_name="키라솔루션즈")
    blind_issues = [i for i in issues if i.category == "blind_violation"]
    assert len(blind_issues) >= 1
    assert "키라솔루션즈" in blind_issues[0].detail


def test_detect_vague_claims():
    text = "최고 수준의 기술력으로 최적화된 시스템을 구축하겠습니다."
    issues = check_quality(text)
    vague = [i for i in issues if i.category == "vague_claim"]
    assert len(vague) >= 1


def test_clean_text_passes():
    text = """## 시스템 아키텍처

본 사업의 시스템은 3-tier 아키텍처(웹서버-WAS-DB)로 구성하며,
가용성 99.9%를 목표로 이중화 구성합니다.

| 구분 | 사양 | 수량 |
|------|------|------|
| 웹서버 | Nginx 1.25 | 2대 |

위 표와 같이 웹서버는 로드밸런서를 통해 이중화합니다."""
    issues = check_quality(text)
    critical = [i for i in issues if i.severity == "critical"]
    assert len(critical) == 0


def test_no_company_name_skip_blind_check():
    text = "당사는 최고의 기술력을 보유하고 있습니다."
    issues = check_quality(text, company_name=None)
    blind_issues = [i for i in issues if i.category == "blind_violation"]
    assert len(blind_issues) == 0


def test_blind_check_word_boundary():
    """'삼성전자' should NOT trigger blind violation when only '삼성전자공업' appears."""
    text = "삼성전자공업은 우수한 기업입니다."
    issues = check_quality(text, company_name="삼성전자")
    blind_issues = [i for i in issues if i.category == "blind_violation"]
    assert len(blind_issues) == 0  # partial match should NOT trigger


def test_blind_check_exact_match():
    """'삼성전자' as standalone word should trigger blind violation."""
    text = "본 제안에서 삼성전자 가 수행합니다."
    issues = check_quality(text, company_name="삼성전자")
    blind_issues = [i for i in issues if i.category == "blind_violation"]
    assert len(blind_issues) >= 1


def test_check_quality_for_doc_type_proposal():
    """Proposal: full blind + ambiguity check."""
    from quality_checker import check_quality_for_doc_type
    issues = check_quality_for_doc_type("좋은 제안서 내용입니다.", "proposal", company_name="테스트회사")
    assert isinstance(issues, list)


def test_check_quality_for_doc_type_execution_plan():
    """execution_plan: ambiguity check only (no blind words)."""
    from quality_checker import check_quality_for_doc_type
    # "최고 수준" is a VAGUE_PATTERNS match → vague_claim category
    issues = check_quality_for_doc_type("최고 수준의 기술력", "execution_plan")
    assert any(i.category == "vague_claim" for i in issues)


def test_check_quality_for_doc_type_presentation():
    """presentation: minimal checks."""
    from quality_checker import check_quality_for_doc_type
    issues = check_quality_for_doc_type("발표 내용", "presentation")
    assert isinstance(issues, list)


def test_check_quality_for_doc_type_track_record():
    """track_record: blind check active."""
    from quality_checker import check_quality_for_doc_type
    issues = check_quality_for_doc_type("테스트회사가 수행한 사업", "track_record", company_name="테스트회사")
    assert any(i.category == "blind_violation" for i in issues)
