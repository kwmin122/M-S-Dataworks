"""
matcher가 req.constraints를 활용해 결정론적으로 판단하는지 검증.
LLM mock으로 실제 API 호출 없이 테스트.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch
from rfx_analyzer import RFxRequirement, RFxConstraint
from matcher import QualificationMatcher, MatchStatus


def _make_matcher_with_context(context_text: str) -> QualificationMatcher:
    mock_rag = MagicMock()
    mock_rag.collection.count.return_value = 1
    mock_rag.search.return_value = [
        MagicMock(text=context_text, source_file="company.pdf")
    ]
    return QualificationMatcher(mock_rag, api_key="test-key")


def test_amount_fail_returns_not_met_without_llm():
    """19.8억 < 20억 기준 → NOT_MET, LLM 미호출"""
    matcher = _make_matcher_with_context(
        "KEPCO 스마트그리드 사업, 계약금액 19.8억원, 2023년 완료"
    )
    req = RFxRequirement(
        category="실적요건",
        description="공공기관 SI 수행실적",
        is_mandatory=True,
        detail="건당 20억원 이상",
        constraints=[
            RFxConstraint("contract_amount", ">=", 20.0, "KRW_100M", "건당 20억원 이상")
        ]
    )
    with patch.object(matcher, '_judge_with_llm') as mock_llm:
        result = matcher._match_single_requirement(req)
    assert result.status == MatchStatus.NOT_MET, f"NOT_MET 기대, 실제: {result.status}"
    mock_llm.assert_not_called()  # LLM 미호출 확인


def test_amount_pass_returns_met_without_llm():
    """20억 == 20억 기준 → MET, LLM 미호출"""
    matcher = _make_matcher_with_context(
        "국방부 물류 사업, 계약금액 20억원, 2023년 완료"
    )
    req = RFxRequirement(
        category="실적요건",
        description="공공기관 SI 수행실적",
        is_mandatory=True,
        detail="건당 20억원 이상",
        constraints=[
            RFxConstraint("contract_amount", ">=", 20.0, "KRW_100M", "건당 20억원 이상")
        ]
    )
    with patch.object(matcher, '_judge_with_llm') as mock_llm:
        result = matcher._match_single_requirement(req)
    assert result.status == MatchStatus.MET, f"MET 기대, 실제: {result.status}"
    mock_llm.assert_not_called()


def test_skip_constraint_falls_back_to_llm():
    """CUSTOM constraint → SKIP → LLM fallback 호출"""
    matcher = _make_matcher_with_context("회사 정보 텍스트")
    req = RFxRequirement(
        category="기타",
        description="특수 조건",
        is_mandatory=True,
        detail="특수 조건 설명",
        constraints=[
            RFxConstraint("CUSTOM", ">=", 1, "", "특수 조건")
        ]
    )
    mock_response = {
        "status": "판단불가",
        "evidence": "정보 부족",
        "confidence": 0.5,
        "preparation_guide": ""
    }
    with patch.object(matcher, '_judge_with_llm', return_value=mock_response) as mock_llm:
        result = matcher._match_single_requirement(req)
    mock_llm.assert_called_once()  # SKIP → LLM 호출 확인


def test_empty_constraints_uses_llm():
    """constraints=[] → LLM fallback (기존 경로 회귀)"""
    matcher = _make_matcher_with_context("ISO 9001 인증 보유")
    req = RFxRequirement(
        category="필수자격",
        description="ISO 9001 유효 인증",
        is_mandatory=True,
        detail="유효한 ISO 9001 인증",
        constraints=[]  # 빈 배열
    )
    mock_response = {
        "status": "충족",
        "evidence": "ISO 9001 보유 확인",
        "confidence": 0.9,
        "preparation_guide": ""
    }
    with patch.object(matcher, '_judge_with_llm', return_value=mock_response) as mock_llm:
        result = matcher._match_single_requirement(req)
    mock_llm.assert_called_once()
