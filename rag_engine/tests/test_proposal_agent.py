"""Planning Agent tests — strategy generation, JSON parsing, fallback."""
import json
from unittest.mock import patch

import pytest

from proposal_agent import ProposalPlanningAgent
from knowledge_models import ProposalStrategy, StrategyMemo, ProposalOutline, ProposalSection


SAMPLE_RFX = {
    "title": "XX 교통관제시스템 구축",
    "issuing_org": "국토교통부",
    "budget": "50억",
    "project_period": "12개월",
    "evaluation_criteria": [
        {"category": "기술적 접근방안", "max_score": 30, "description": "시스템 구축"},
        {"category": "수행관리", "max_score": 20, "description": "프로젝트 관리"},
    ],
}

SAMPLE_OUTLINE = ProposalOutline(
    title="XX 교통관제시스템 구축",
    issuing_org="국토교통부",
    sections=[
        ProposalSection(name="기술적 접근방안", evaluation_item="시스템 구축", max_score=30, weight=0.6),
        ProposalSection(name="수행관리", evaluation_item="프로젝트 관리", max_score=20, weight=0.4),
    ],
)


class TestProposalStrategy:
    def test_get_memo_for_existing(self):
        strategy = ProposalStrategy(
            overall_approach="test",
            section_strategies=[
                StrategyMemo(section_name="A", emphasis_points=["x"]),
                StrategyMemo(section_name="B", emphasis_points=["y"]),
            ],
        )
        memo = strategy.get_memo_for("A")
        assert memo is not None
        assert memo.emphasis_points == ["x"]

    def test_get_memo_for_missing(self):
        strategy = ProposalStrategy(
            overall_approach="test",
            section_strategies=[StrategyMemo(section_name="A")],
        )
        assert strategy.get_memo_for("Z") is None

    def test_empty_strategy(self):
        strategy = ProposalStrategy()
        assert strategy.overall_approach == ""
        assert len(strategy.section_strategies) == 0
        assert strategy.get_memo_for("any") is None


class TestPlanningAgent:
    def test_generate_strategy_parses_valid_json(self):
        agent = ProposalPlanningAgent()
        mock_json = json.dumps({
            "overall_approach": "교통 전문성 강조",
            "strengths_mapping": {"ITS 경험": "기술적 접근방안"},
            "section_strategies": [
                {
                    "section_name": "기술적 접근방안",
                    "emphasis_points": ["ITS 특허 3건"],
                    "differentiators": ["유지보수 인력 2배"],
                    "risk_notes": ["예산 초과 주의"],
                    "knowledge_hints": ["교통신호제어"],
                },
                {
                    "section_name": "수행관리",
                    "emphasis_points": ["PM 자격 보유"],
                    "differentiators": [],
                    "risk_notes": [],
                    "knowledge_hints": ["프로젝트 관리"],
                },
            ],
        })

        with patch.object(agent, "_call_llm", return_value=mock_json):
            strategy = agent.generate_strategy(
                rfx_result=SAMPLE_RFX,
                outline=SAMPLE_OUTLINE,
                company_context="ITS 10년 경력, 특허 3건",
            )
            assert strategy.overall_approach == "교통 전문성 강조"
            assert "ITS 경험" in strategy.strengths_mapping
            assert len(strategy.section_strategies) == 2
            memo = strategy.get_memo_for("기술적 접근방안")
            assert memo is not None
            assert "ITS 특허 3건" in memo.emphasis_points

    def test_generate_strategy_handles_markdown_fenced_json(self):
        agent = ProposalPlanningAgent()
        fenced = '```json\n{"overall_approach": "test", "strengths_mapping": {}, "section_strategies": []}\n```'

        with patch.object(agent, "_call_llm", return_value=fenced):
            strategy = agent.generate_strategy(
                rfx_result=SAMPLE_RFX, outline=SAMPLE_OUTLINE,
            )
            assert strategy.overall_approach == "test"

    def test_generate_strategy_json_parse_error_fallback(self):
        agent = ProposalPlanningAgent()

        with patch.object(agent, "_call_llm", return_value="not valid json {{{"):
            strategy = agent.generate_strategy(
                rfx_result=SAMPLE_RFX, outline=SAMPLE_OUTLINE,
            )
            # Graceful fallback: empty strategy, no crash
            assert strategy.overall_approach == ""
            assert len(strategy.section_strategies) == 0

    def test_generate_strategy_empty_company_context(self):
        agent = ProposalPlanningAgent()
        mock_json = json.dumps({
            "overall_approach": "일반 전략",
            "strengths_mapping": {},
            "section_strategies": [],
        })

        with patch.object(agent, "_call_llm", return_value=mock_json):
            strategy = agent.generate_strategy(
                rfx_result=SAMPLE_RFX, outline=SAMPLE_OUTLINE, company_context="",
            )
            assert strategy.overall_approach == "일반 전략"

    def test_parse_strategy_missing_fields(self):
        agent = ProposalPlanningAgent()
        # JSON with missing optional fields
        partial = json.dumps({"overall_approach": "partial", "section_strategies": [
            {"section_name": "X"}  # missing emphasis_points etc.
        ]})
        strategy = agent._parse_strategy(partial)
        assert strategy.overall_approach == "partial"
        assert len(strategy.section_strategies) == 1
        assert strategy.section_strategies[0].emphasis_points == []
