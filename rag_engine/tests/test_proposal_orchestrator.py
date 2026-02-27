from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch, MagicMock
from proposal_orchestrator import generate_proposal, ProposalResult


def _mock_rfx():
    return {
        "title": "테스트 정보시스템 구축",
        "issuing_org": "테스트기관",
        "budget": "3억원",
        "project_period": "8개월",
        "evaluation_criteria": [
            {"category": "사업 이해도", "max_score": 15, "description": "사업 이해"},
            {"category": "기술성", "max_score": 40, "description": "구현방안"},
        ],
        "requirements": [],
        "rfp_text_summary": "클라우드 기반 시스템 구축 사업",
    }


@patch("proposal_orchestrator.write_section")
@patch("proposal_orchestrator.KnowledgeDB")
def test_generate_proposal_returns_result(mock_kb_class, mock_write):
    mock_kb = MagicMock()
    mock_kb.search.return_value = []
    mock_kb_class.return_value = mock_kb
    mock_write.return_value = "## 섹션 내용\n\n테스트 내용입니다."

    result = generate_proposal(
        rfx_result=_mock_rfx(),
        output_dir="/tmp/test_proposals",
    )
    assert isinstance(result, ProposalResult)
    assert result.docx_path.endswith(".docx")
    assert len(result.sections) >= 2
    assert result.quality_issues is not None


@patch("proposal_orchestrator.write_section")
@patch("proposal_orchestrator.KnowledgeDB")
def test_generate_proposal_calls_section_writer_per_section(mock_kb_class, mock_write):
    mock_kb = MagicMock()
    mock_kb.search.return_value = []
    mock_kb_class.return_value = mock_kb
    mock_write.return_value = "내용"

    result = generate_proposal(
        rfx_result=_mock_rfx(),
        output_dir="/tmp/test_proposals",
    )
    assert mock_write.call_count >= 2
