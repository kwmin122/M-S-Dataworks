"""Proposal Planning Agent — strategic analysis before section writing.

Generates ProposalStrategy with per-section StrategyMemos via single LLM call.
Falls back to empty strategy on parse failure (graceful degradation).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from openai import OpenAI

from knowledge_models import (
    ProposalOutline,
    ProposalStrategy,
    StrategyMemo,
)
from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

STRATEGY_SYSTEM_PROMPT = """당신은 대한민국 공공조달 입찰 전략 수립 전문가입니다.
RFP 분석 결과와 회사 역량을 바탕으로 제안서 전략을 수립합니다.

반드시 아래 JSON 형식으로만 응답하세요. 설명이나 마크다운 없이 순수 JSON만:

{
  "overall_approach": "전체 제안 전략 요약 (1-2문장)",
  "strengths_mapping": {"회사강점1": "매핑될 평가항목", ...},
  "section_strategies": [
    {
      "section_name": "정확한 섹션 이름",
      "emphasis_points": ["이 섹션에서 강조할 포인트"],
      "differentiators": ["경쟁 차별화 요소"],
      "risk_notes": ["주의사항"],
      "knowledge_hints": ["Layer1 검색 키워드 힌트"]
    }
  ]
}"""

FEW_SHOT_EXAMPLE = """예시 응답:
{
  "overall_approach": "스마트시티 특화 기술력과 10년 ITS 실적을 앞세워 기술점수 극대화",
  "strengths_mapping": {
    "ITS 구축 실적 50건": "기술적 접근방안",
    "PM 자격 보유 인력 3명": "수행관리"
  },
  "section_strategies": [
    {
      "section_name": "기술적 접근방안",
      "emphasis_points": ["자체 특허 3건 활용 방안", "유사 사업 성공 사례 제시"],
      "differentiators": ["경쟁사 대비 유지보수 인력 2배"],
      "risk_notes": ["예산 범위 내 기술 제안 필수"],
      "knowledge_hints": ["교통신호제어", "ITS 아키텍처"]
    }
  ]
}"""


class ProposalPlanningAgent:
    """Strategic planning agent for proposal generation.

    Phase 1+2 combined: single LLM call generates full ProposalStrategy JSON.
    Falls back to empty strategy on parse failure.
    """

    def __init__(self, api_key: Optional[str] = None, middleware=None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.middleware = middleware

    def generate_strategy(
        self,
        rfx_result: dict[str, Any],
        outline: ProposalOutline,
        company_context: str = "",
    ) -> ProposalStrategy:
        """Generate complete proposal strategy in one LLM call."""
        section_names = [s.name for s in outline.sections]
        section_info = "\n".join(
            f"- {s.name} (배점 {s.max_score}점, 비중 {s.weight:.0%}): {s.evaluation_item}"
            for s in outline.sections
        )

        user_prompt = (
            f"## RFP 정보\n"
            f"공고명: {rfx_result.get('title', '')}\n"
            f"발주기관: {rfx_result.get('issuing_org', '')}\n"
            f"예산: {rfx_result.get('budget', '미정')}\n"
            f"사업기간: {rfx_result.get('project_period', '미정')}\n\n"
            f"## 평가항목\n{section_info}\n\n"
            f"## 회사 역량\n{company_context or '정보 없음'}\n\n"
            f"{FEW_SHOT_EXAMPLE}\n\n"
            f"위 정보를 바탕으로 제안서 전략을 수립하세요. "
            f"section_strategies의 section_name은 반드시 다음 목록에서 선택: {section_names}"
        )

        raw = self._call_llm(user_prompt)
        return self._parse_strategy(raw)

    def _call_llm(self, user_prompt: str) -> str:
        client = OpenAI(api_key=self.api_key, timeout=LLM_DEFAULT_TIMEOUT)

        def _do_call():
            return client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": STRATEGY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=3000,
            )

        fn = _do_call
        if self.middleware:
            fn = self.middleware.wrap(_do_call, caller_name="proposal_agent")
        resp = call_with_retry(fn)
        return resp.choices[0].message.content or ""

    def _parse_strategy(self, raw: str) -> ProposalStrategy:
        """Parse JSON response into ProposalStrategy. Fallback to empty on failure."""
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # Remove first line (```json) and last line (```)
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            data = json.loads(cleaned)

            sections = []
            for s in data.get("section_strategies", []):
                sections.append(StrategyMemo(
                    section_name=s.get("section_name", ""),
                    emphasis_points=s.get("emphasis_points", []),
                    differentiators=s.get("differentiators", []),
                    risk_notes=s.get("risk_notes", []),
                    knowledge_hints=s.get("knowledge_hints", []),
                ))

            return ProposalStrategy(
                overall_approach=data.get("overall_approach", ""),
                strengths_mapping=data.get("strengths_mapping", {}),
                section_strategies=sections,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Strategy JSON parse failed, using empty strategy: %s", exc)
            return ProposalStrategy()
