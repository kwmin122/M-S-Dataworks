"""Proposal Planner — RFP evaluation criteria to section outline.

Takes RFxAnalysisResult and generates a ProposalOutline — ordered list
of sections mapped to evaluation criteria with page targets.
"""
from __future__ import annotations

from typing import Any

from knowledge_models import ProposalOutline, ProposalSection

# Standard fallback sections when no evaluation criteria available
DEFAULT_SECTIONS = [
    ("제안 개요", 10),
    ("사업 이해도", 15),
    ("기술적 접근방안", 35),
    ("수행관리 방안", 15),
    ("투입인력 및 조직", 10),
    ("유사 수행실적", 10),
    ("기타 특이사항", 5),
]

# Categories that are scoring buckets, not proposal content sections.
# These should be filtered out — "가격평가" is not a section you write.
_NON_CONTENT_KEYWORDS = {"가격", "가격평가", "가격점수", "입찰가격"}

# High-level bucket names that indicate coarse extraction
_COARSE_KEYWORDS = {"기술평가", "기술", "기술점수", "제안평가", "종합평가"}


def _is_criteria_too_coarse(eval_criteria: list[dict[str, Any]]) -> bool:
    """Detect when extracted eval_criteria are too high-level to be useful sections.

    Returns True when criteria are just scoring buckets (기술평가/가격평가)
    rather than actionable proposal sections (사업이해도/기술적 접근방안).
    """
    content = [
        ec for ec in eval_criteria
        if ec.get("category", "").strip() not in _NON_CONTENT_KEYWORDS
        and ec.get("parent_category", "").strip() not in _NON_CONTENT_KEYWORDS
    ]
    if not content:
        return True
    # Check if all remaining are just bucket names
    names = {ec.get("category", "").strip() for ec in content}
    if names <= _COARSE_KEYWORDS:
        return True
    # If ≤2 content sections, probably too coarse
    if len(content) <= 2 and names & _COARSE_KEYWORDS:
        return True
    return False


def build_proposal_outline(
    rfx_result: dict[str, Any],
    total_pages: int = 50,
) -> ProposalOutline:
    """Build a ProposalOutline from RFxAnalysisResult dict.

    Maps evaluation criteria to sections with proportional page allocation.
    Falls back to DEFAULT_SECTIONS when criteria are missing or too coarse
    (e.g., only "기술평가"/"가격평가" — these are scoring buckets, not sections).
    """
    title = rfx_result.get("title", "제안서")
    issuing_org = rfx_result.get("issuing_org", "")
    eval_criteria = rfx_result.get("evaluation_criteria", [])

    sections: list[ProposalSection] = []

    # Filter out non-content criteria (가격평가 is not a proposal section)
    content_criteria = [
        ec for ec in eval_criteria
        if ec.get("category", "").strip() not in _NON_CONTENT_KEYWORDS
        and ec.get("parent_category", "").strip() not in _NON_CONTENT_KEYWORDS
    ]

    if content_criteria and not _is_criteria_too_coarse(eval_criteria):
        total_score = sum(ec.get("max_score", 0) for ec in content_criteria) or 100
        for ec in content_criteria:
            name = ec.get("category", ec.get("name", "섹션"))
            max_score = ec.get("max_score", 0)
            weight = max_score / total_score if total_score else 0
            sections.append(ProposalSection(
                name=name,
                evaluation_item=ec.get("description", ""),
                max_score=max_score,
                weight=round(weight, 3),
                instructions=f"RFP 평가항목 '{name}'에 맞춰 작성. 배점 {max_score}점.",
            ))
    else:
        # Use well-structured default sections
        total_score = sum(s for _, s in DEFAULT_SECTIONS)
        for name, score in DEFAULT_SECTIONS:
            sections.append(ProposalSection(
                name=name,
                evaluation_item=name,
                max_score=score,
                weight=round(score / total_score, 3),
            ))

    # Always prepend overview if not present
    has_overview = any("요약" in s.name or "개요" in s.name for s in sections)
    if not has_overview:
        sections.insert(0, ProposalSection(
            name="제안 개요",
            evaluation_item="Executive Summary",
            max_score=0,
            weight=0.05,
            instructions="전체 제안의 핵심을 1~2페이지로 요약. 평가위원이 가장 먼저 보는 부분.",
        ))

    # Normalize weights
    total_weight = sum(s.weight for s in sections) or 1
    for s in sections:
        s.weight = round(s.weight / total_weight, 3)

    return ProposalOutline(
        title=title,
        issuing_org=issuing_org,
        sections=sections,
        total_pages_target=total_pages,
    )
