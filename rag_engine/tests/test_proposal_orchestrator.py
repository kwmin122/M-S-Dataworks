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


def test_generate_proposal_with_profile_md(tmp_path):
    """company_skills_dir 지정 시 profile.md가 section_writer에 전달."""
    # Create a profile.md
    skills_dir = str(tmp_path / "skills" / "comp_001")
    os.makedirs(skills_dir, exist_ok=True)
    with open(os.path.join(skills_dir, "profile.md"), "w") as f:
        f.write("## 문체\n- 어미: ~합니다")

    rfx = {"title": "테스트 사업", "issuing_org": "기관"}
    mock_kb = MagicMock()
    mock_kb.search.return_value = []

    with patch("proposal_orchestrator.KnowledgeDB", return_value=mock_kb), \
         patch("proposal_orchestrator.write_section") as mock_write, \
         patch("proposal_orchestrator.build_proposal_outline") as mock_outline, \
         patch("proposal_orchestrator.assemble_docx", return_value=str(tmp_path / "out.docx")):
        from knowledge_models import ProposalSection, ProposalOutline
        mock_outline.return_value = ProposalOutline(
            title="테스트",
            issuing_org="기관",
            sections=[ProposalSection(name="개요", evaluation_item="이해도", max_score=10, weight=0.1)],
        )
        mock_write.return_value = "내용"

        from proposal_orchestrator import generate_proposal
        result = generate_proposal(
            rfx_result=rfx,
            output_dir=str(tmp_path),
            knowledge_db_path=str(tmp_path / "kb"),
            company_skills_dir=skills_dir,
        )

        # write_section이 profile_md와 함께 호출됐는지 확인
        assert mock_write.called
        _, kwargs = mock_write.call_args
        assert "합니다" in kwargs.get("profile_md", "")
