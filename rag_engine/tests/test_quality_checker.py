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
