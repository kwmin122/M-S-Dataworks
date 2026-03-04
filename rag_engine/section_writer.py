"""Section Writer — Layer 1 knowledge-augmented proposal generation.

Generates one proposal section at a time by retrieving relevant
Layer 1 knowledge, assembling a multi-layer prompt, and calling LLM.
"""
from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from knowledge_models import KnowledgeUnit, ProposalSection, StrategyMemo
from llm_utils import call_with_retry, LLM_DEFAULT_TIMEOUT

SYSTEM_PROMPT = """당신은 대한민국 공공조달 기술제안서 작성 전문가입니다.
평가위원이 높은 점수를 줄 수 있도록, 구체적이고 전문적인 제안서 섹션을 작성합니다.
모든 주장에는 근거를 제시하고, 추상적 표현을 피합니다.
마크다운 형식으로 작성하되, 제안서 특성에 맞게 표, 목록, 강조를 활용합니다."""


def _build_customization_checklist(section: ProposalSection, knowledge: list[KnowledgeUnit]) -> str:
    """Build customization checklist for template mode."""
    parts = []

    # Customization checkboxes
    parts.append("⚠️ **회사 맞춤 수정 필요:**")
    parts.append("- [ ] 우리 회사의 관련 실적 및 경험 추가")
    parts.append("- [ ] 우리 회사만의 기술력과 전문성 강조")
    parts.append("- [ ] 차별화된 제안 방법론 또는 접근법 서술")
    parts.append("")

    # Knowledge tips
    if knowledge:
        parts.append("💡 **작성 팁 (공공조달 지식):**")
        for k in knowledge[:5]:  # Top 5 knowledge units
            if k.rule:
                parts.append(f"• {k.rule}")
        parts.append("")

    return "\n".join(parts)


def _assemble_prompt(
    section: ProposalSection,
    knowledge: list[KnowledgeUnit],
    rfp_context: str,
    company_context: str = "",
    profile_md: str = "",
    strategy_memo: Optional[StrategyMemo] = None,
    total_pages: int = 50,
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

    # Profile — company skill file (profile.md)
    if profile_md:
        parts.append(f"## 이 회사의 제안서 프로필 (반드시 준수):\n{profile_md}")

    # Strategy memo (from Planning Agent)
    if strategy_memo:
        memo_parts = []
        if strategy_memo.emphasis_points:
            memo_parts.append("강조 포인트: " + ", ".join(strategy_memo.emphasis_points))
        if strategy_memo.differentiators:
            memo_parts.append("차별화 요소: " + ", ".join(strategy_memo.differentiators))
        if strategy_memo.risk_notes:
            memo_parts.append("주의사항: " + ", ".join(strategy_memo.risk_notes))
        if memo_parts:
            parts.append("## 이 섹션의 전략 (반드시 반영):\n" + "\n".join(memo_parts))

    # RFP context
    parts.append(f"## 이번 공고 정보:\n{rfp_context}")

    # Task
    page_target = max(1, int(section.weight * total_pages))
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


def _call_llm_for_section(prompt: str, api_key: Optional[str] = None, middleware=None) -> str:
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

    # call_with_retry INSIDE middleware — retry must see raw OpenAI errors,
    # not LLMError from middleware wrapping.
    retried = lambda: call_with_retry(_do_call)
    fn = middleware.wrap(retried, caller_name="section_writer") if middleware else retried
    resp = fn()
    return resp.choices[0].message.content or ""


def write_section(
    section: ProposalSection,
    rfp_context: str,
    knowledge: list[KnowledgeUnit],
    company_context: str = "",
    api_key: Optional[str] = None,
    profile_md: str = "",
    strategy_memo: Optional[StrategyMemo] = None,
    middleware=None,
    total_pages: int = 50,
    template_mode: bool = False,
) -> str:
    """Generate one proposal section with Layer 1 knowledge injection.

    Args:
        template_mode: If True, generates generic draft with customization checkboxes.
    """
    # In template mode, ignore company_context and profile_md
    if template_mode:
        prompt = _assemble_prompt(section, knowledge, rfp_context, company_context="", profile_md="", strategy_memo=strategy_memo, total_pages=total_pages)
        base_text = _call_llm_for_section(prompt, api_key, middleware=middleware)

        # Add customization checklist
        customization_section = _build_customization_checklist(section, knowledge)
        return base_text + "\n\n" + customization_section
    else:
        prompt = _assemble_prompt(section, knowledge, rfp_context, company_context, profile_md, strategy_memo, total_pages=total_pages)
        return _call_llm_for_section(prompt, api_key, middleware=middleware)


def rewrite_section(
    section: ProposalSection,
    rfp_context: str,
    knowledge: list[KnowledgeUnit],
    company_context: str = "",
    api_key: Optional[str] = None,
    profile_md: str = "",
    original_text: str = "",
    issues: Optional[list] = None,
    strategy_memo: Optional[StrategyMemo] = None,
    middleware=None,
    total_pages: int = 50,
) -> str:
    """Rewrite a section incorporating quality checker feedback.

    Builds the same prompt as write_section but appends the original text
    and specific issues to fix. Max 1 rewrite per section.
    """
    base_prompt = _assemble_prompt(section, knowledge, rfp_context, company_context, profile_md, strategy_memo, total_pages=total_pages)

    fix_instructions = []
    for issue in (issues or []):
        fix_instructions.append(
            f"- [{issue.category}] {issue.detail}"
            + (f" → 수정방법: {issue.suggestion}" if issue.suggestion else "")
        )

    rewrite_prompt = (
        base_prompt
        + "\n\n## 이전 생성 결과 (수정 필요):\n"
        + original_text
        + "\n\n## 발견된 문제점 — 반드시 수정하세요:\n"
        + "\n".join(fix_instructions)
        + "\n\n위 문제점을 모두 수정한 새 버전을 작성하세요. 전체 섹션을 다시 작성합니다."
    )

    return _call_llm_for_section(rewrite_prompt, api_key, middleware=middleware)
