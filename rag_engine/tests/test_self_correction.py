"""Self-Correction Loop tests — quality check → rewrite → residual tagging."""
from unittest.mock import patch, MagicMock

import pytest

from section_writer import rewrite_section
from knowledge_models import ProposalSection, KnowledgeUnit, KnowledgeCategory, SourceType
from quality_checker import QualityIssue


class TestRewriteSection:
    def test_rewrite_injects_issues_into_prompt(self):
        section = ProposalSection(
            name="기술적 접근방안",
            evaluation_item="시스템 구축",
            max_score=20,
            weight=0.3,
        )
        issues = [
            QualityIssue(
                category="blind_violation",
                severity="critical",
                detail="회사명 '삼성전자' 이 제안서 본문에 노출됨",
                suggestion="'삼성전자'를 '당사'로 교체",
            )
        ]
        original_text = "삼성전자는 이 사업을 수행할 능력이 있습니다."

        with patch("section_writer._call_llm_for_section") as mock_llm:
            mock_llm.return_value = "당사는 이 사업을 수행할 능력이 있습니다."
            result = rewrite_section(
                section=section,
                rfp_context="테스트 RFP",
                knowledge=[],
                company_context="",
                original_text=original_text,
                issues=issues,
            )
            assert result == "당사는 이 사업을 수행할 능력이 있습니다."
            # Verify issues were included in the prompt
            call_args = mock_llm.call_args[0][0]
            assert "blind_violation" in call_args
            assert "삼성전자" in call_args
            assert "수정방법" in call_args

    def test_rewrite_with_empty_issues(self):
        section = ProposalSection(
            name="테스트", evaluation_item="테스트", max_score=10, weight=0.1,
        )
        with patch("section_writer._call_llm_for_section") as mock_llm:
            mock_llm.return_value = "rewritten"
            result = rewrite_section(
                section=section, rfp_context="", knowledge=[],
                original_text="original", issues=[],
            )
            assert result == "rewritten"


class TestWriteAndCheckSection:
    @patch("proposal_orchestrator.write_section")
    @patch("proposal_orchestrator.check_quality")
    @patch("proposal_orchestrator.rewrite_section")
    def test_critical_triggers_rewrite(self, mock_rewrite, mock_check, mock_write):
        from proposal_orchestrator import _write_and_check_section

        section = ProposalSection(
            name="테스트", evaluation_item="테스트", max_score=10, weight=0.1
        )
        mock_write.return_value = "bad text with 회사명"
        mock_check.side_effect = [
            [QualityIssue(category="blind_violation", severity="critical",
                          detail="회사명 노출", suggestion="교체 필요")],
            [],  # After rewrite: no issues
        ]
        mock_rewrite.return_value = "fixed text"

        name, text, residuals = _write_and_check_section(
            section=section, rfp_context="", knowledge=[], company_context="",
            api_key=None, profile_md="", company_name="테스트회사",
        )
        assert text == "fixed text"
        assert len(residuals) == 0
        mock_rewrite.assert_called_once()

    @patch("proposal_orchestrator.write_section")
    @patch("proposal_orchestrator.check_quality")
    def test_warning_only_skips_rewrite(self, mock_check, mock_write):
        from proposal_orchestrator import _write_and_check_section

        section = ProposalSection(
            name="테스트", evaluation_item="테스트", max_score=10, weight=0.1
        )
        mock_write.return_value = "최고 수준의 기술력"
        mock_check.return_value = [
            QualityIssue(category="vague_claim", severity="warning",
                         detail="근거 없는 추상 표현", suggestion="수치 추가")
        ]

        name, text, residuals = _write_and_check_section(
            section=section, rfp_context="", knowledge=[], company_context="",
            api_key=None, profile_md="", company_name=None,
        )
        assert text == "최고 수준의 기술력"  # No rewrite
        assert len(residuals) == 0

    @patch("proposal_orchestrator.write_section")
    @patch("proposal_orchestrator.check_quality")
    @patch("proposal_orchestrator.rewrite_section")
    def test_residual_critical_after_rewrite(self, mock_rewrite, mock_check, mock_write):
        from proposal_orchestrator import _write_and_check_section

        section = ProposalSection(
            name="테스트", evaluation_item="테스트", max_score=10, weight=0.1
        )
        mock_write.return_value = "bad text"
        mock_check.side_effect = [
            [QualityIssue(category="blind_violation", severity="critical",
                          detail="회사명 노출", suggestion="교체")],
            [QualityIssue(category="blind_violation", severity="critical",
                          detail="회사명 여전히 노출", suggestion="교체")],
        ]
        mock_rewrite.return_value = "still bad text"

        name, text, residuals = _write_and_check_section(
            section=section, rfp_context="", knowledge=[], company_context="",
            api_key=None, profile_md="", company_name="회사명",
        )
        assert text == "still bad text"
        assert len(residuals) == 1
        assert residuals[0].detail == "회사명 여전히 노출"

    @patch("proposal_orchestrator.write_section")
    @patch("proposal_orchestrator.check_quality")
    def test_no_issues_no_rewrite(self, mock_check, mock_write):
        from proposal_orchestrator import _write_and_check_section

        section = ProposalSection(
            name="좋은섹션", evaluation_item="좋은항목", max_score=10, weight=0.1
        )
        mock_write.return_value = "perfect text"
        mock_check.return_value = []  # No issues at all

        name, text, residuals = _write_and_check_section(
            section=section, rfp_context="", knowledge=[], company_context="",
            api_key=None, profile_md="", company_name=None,
        )
        assert text == "perfect text"
        assert len(residuals) == 0
