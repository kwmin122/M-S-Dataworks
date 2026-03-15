"""Quality Checker — Anti-pattern gate for proposal text.

Checks for common pitfalls: blind evaluation violations, vague claims
without evidence, missing table explanations.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


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
    #    Korean-aware word boundary: block matches that are part of a longer
    #    content word (e.g. "삼성전자공업") but ALLOW grammatical particles
    #    (은/는/이/가/을/를/의/에/로/와/과/도/만 etc.) to follow the name.
    _KO_PARTICLES = r"은|는|이|가|을|를|의|에|로|으로|와|과|도|만|에서|까지|부터|처럼|보다|라|란|나|님"
    if company_name:
        blind_pattern = re.compile(
            r"(?<![가-힣a-zA-Z0-9])"
            + re.escape(company_name)
            + r"(?=(?:" + _KO_PARTICLES + r")?(?![가-힣]))"
        )
        if blind_pattern.search(text):
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


# Doc-type-aware quality rules
_DOC_TYPE_CHECKS: dict[str, dict] = {
    "proposal": {"blind": True, "ambiguity": True},
    "execution_plan": {"blind": False, "ambiguity": True},
    "presentation": {"blind": False, "ambiguity": False},
    "track_record": {"blind": True, "ambiguity": True},
    "checklist": {"blind": False, "ambiguity": False},
}


def check_quality_for_doc_type(
    text: str,
    doc_type: str,
    company_name: str | None = None,
    custom_forbidden: list[str] | None = None,
) -> list[QualityIssue]:
    """Run quality checks appropriate for the given doc_type.

    Composes with existing check_quality() rather than duplicating logic.
    proposal/track_record: blind + ambiguity checks.
    execution_plan: ambiguity only.
    presentation/checklist: minimal (custom_forbidden only).
    """
    checks = _DOC_TYPE_CHECKS.get(doc_type, {"blind": True, "ambiguity": True})
    issues: list[QualityIssue] = []

    # Compose with existing check_quality() — pass company_name only when blind check enabled
    if checks.get("blind") or checks.get("ambiguity"):
        base_issues = check_quality(
            text,
            company_name=company_name if checks.get("blind") else None,
        )
        # Filter out vague_claim if ambiguity check is disabled
        if not checks.get("ambiguity"):
            base_issues = [i for i in base_issues if i.category != "vague_claim"]
        # Filter out blind_violation if blind check is disabled
        if not checks.get("blind"):
            base_issues = [i for i in base_issues if i.category != "blind_violation"]
        issues.extend(base_issues)

    if custom_forbidden:
        for pattern in custom_forbidden:
            if pattern in text:
                issues.append(QualityIssue(
                    category="custom_forbidden",
                    severity="warning",
                    detail=f"금지 표현 발견: {pattern}",
                    location="",
                ))

    return issues


def check_quality_with_pack(
    text: str,
    company_name: Optional[str] = None,
    must_include_facts: Optional[list[str]] = None,
    forbidden_patterns: Optional[list[str]] = None,
    min_chars: int = 0,
    max_chars: int = 0,
) -> list[QualityIssue]:
    """Pack-aware quality check extending base check_quality().

    Adds: must_include_facts, forbidden_patterns, length constraints.
    """
    # Start with existing checks
    issues = check_quality(text, company_name)

    # Must-include facts
    for fact in (must_include_facts or []):
        if fact not in text:
            issues.append(QualityIssue(
                category="missing_fact",
                severity="warning",
                detail=f"필수 포함 사실 '{fact}' 미발견",
                suggestion=f"'{fact}'에 대한 내용을 추가하세요",
            ))

    # Forbidden patterns
    for pattern in (forbidden_patterns or []):
        try:
            if re.search(pattern, text):
                issues.append(QualityIssue(
                    category="forbidden_pattern",
                    severity="warning",
                    detail=f"금지 패턴 '{pattern}' 발견",
                    suggestion="해당 표현을 구체적/전문적 표현으로 교체",
                ))
        except re.error as e:
            logger.warning("Invalid forbidden_pattern regex %r in pack config: %s", pattern, e)

    # Length constraints
    text_len = len(text)
    if min_chars and text_len < min_chars:
        issues.append(QualityIssue(
            category="length_violation",
            severity="warning",
            detail=f"텍스트 길이({text_len}자)가 최소 기준({min_chars}자) 미달",
            suggestion=f"최소 {min_chars}자 이상으로 보강",
        ))
    if max_chars and text_len > max_chars:
        issues.append(QualityIssue(
            category="length_violation",
            severity="info",
            detail=f"텍스트 길이({text_len}자)가 최대 기준({max_chars}자) 초과",
            suggestion=f"핵심 내용 중심으로 {max_chars}자 이내로 축소",
        ))

    return issues
