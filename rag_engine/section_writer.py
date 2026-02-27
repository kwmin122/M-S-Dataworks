"""Section Writer — Layer 1 knowledge-augmented proposal generation.

Generates one proposal section at a time by retrieving relevant
Layer 1 knowledge, assembling a multi-layer prompt, and calling LLM.
"""
from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from knowledge_models import KnowledgeUnit, ProposalSection
from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT

SYSTEM_PROMPT = """당신은 대한민국 공공조달 기술제안서 작성 전문가입니다.
평가위원이 높은 점수를 줄 수 있도록, 구체적이고 전문적인 제안서 섹션을 작성합니다.
모든 주장에는 근거를 제시하고, 추상적 표현을 피합니다.
마크다운 형식으로 작성하되, 제안서 특성에 맞게 표, 목록, 강조를 활용합니다."""


def _assemble_prompt(
    section: ProposalSection,
    knowledge: list[KnowledgeUnit],
    rfp_context: str,
    company_context: str = "",
) -> str:
    """Assemble multi-layer prompt for section writing."""
    parts: list[str] = []

    # Layer 1 — retrieved universal knowledge
    if knowledge:
        rules = []
        pitfalls = []
        examples = []
        for k in knowledge:
            if k.category.value == "pitfall":
                pitfalls.append(f"- {k.rule}")
            else:
                rules.append(f"- {k.rule} — {k.explanation}")
            if k.example_good:
                examples.append(f"- 좋은 예시: {k.example_good}")

        if rules:
            parts.append("## 이 유형의 제안서에 적용할 핵심 규칙:\n" + "\n".join(rules))
        if pitfalls:
            parts.append("## 흔한 실수 (반드시 피할 것):\n" + "\n".join(pitfalls))
        if examples:
            parts.append("## 참고할 좋은 예시:\n" + "\n".join(examples))

    # Layer 2 — company context + learned patterns
    if company_context:
        parts.append(f"## 이 회사의 과거 제안서 스타일 및 역량:\n{company_context}")

    # RFP context
    parts.append(f"## 이번 공고 정보:\n{rfp_context}")

    # Task
    page_target = max(1, int(section.weight * 50))
    parts.append(
        f"## 작성할 섹션: {section.name}\n"
        f"평가항목: {section.evaluation_item}\n"
        f"배점: {section.max_score}점\n"
        f"목표 분량: 약 {page_target}페이지\n"
        f"위 규칙과 컨텍스트를 반영하여 이 섹션을 작성하세요."
    )
    if section.instructions:
        parts.append(f"추가 지침: {section.instructions}")

    return "\n\n".join(parts)


def _call_llm_for_section(prompt: str, api_key: Optional[str] = None) -> str:
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        timeout=LLM_DEFAULT_TIMEOUT,
    )

    def _do_call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=4000,
        )

    resp = call_with_retry(_do_call)
    return resp.choices[0].message.content or ""


def write_section(
    section: ProposalSection,
    rfp_context: str,
    knowledge: list[KnowledgeUnit],
    company_context: str = "",
    api_key: Optional[str] = None,
) -> str:
    """Generate one proposal section with Layer 1 knowledge injection."""
    prompt = _assemble_prompt(section, knowledge, rfp_context, company_context)
    return _call_llm_for_section(prompt, api_key)
