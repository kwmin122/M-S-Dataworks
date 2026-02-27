"""Quality Checker — Anti-pattern gate for proposal text.

Checks for common pitfalls: blind evaluation violations, vague claims
without evidence, missing table explanations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class QualityIssue:
    category: str       # blind_violation | vague_claim | missing_explanation | format_error
    severity: str       # critical | warning | info
    detail: str
    location: str = ""  # approximate location in text
    suggestion: str = ""


# Vague claim patterns — phrases that lack evidence
VAGUE_PATTERNS = [
    r"최고\s*수준",
    r"최적화된",
    r"혁신적인",
    r"차별화된\s*기술력",
    r"탁월한\s*역량",
    r"풍부한\s*경험",
    r"우수한\s*인력",
]

VAGUE_RE = re.compile("|".join(VAGUE_PATTERNS), re.IGNORECASE)


def check_quality(
    text: str,
    company_name: Optional[str] = None,
) -> list[QualityIssue]:
    """Run anti-pattern checks on generated proposal text."""
    issues: list[QualityIssue] = []

    # 1. Blind evaluation violation: company name/brand in text
    if company_name and company_name in text:
        issues.append(QualityIssue(
            category="blind_violation",
            severity="critical",
            detail=f"회사명 '{company_name}' 이 제안서 본문에 노출됨",
            suggestion=f"'{company_name}'을 '당사' 또는 '[제안사]'로 교체",
        ))

    # 2. Vague claims without evidence
    for match in VAGUE_RE.finditer(text):
        after = text[match.end():match.end() + 200]
        has_evidence = bool(re.search(r"\d+[%건명억만회]", after))
        if not has_evidence:
            issues.append(QualityIssue(
                category="vague_claim",
                severity="warning",
                detail=f"근거 없는 추상 표현: '{match.group()}'",
                location=f"offset {match.start()}",
                suggestion="구체적 수치, 사례, 또는 출처를 추가하세요",
            ))

    return issues
