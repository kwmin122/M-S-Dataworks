"""Quality Gate — Multi-dimensional quality scoring for generated documents.

Runs after generation, before marking as complete. Produces a structured
quality report with pass/fail/warning for each dimension.

Usage:
    from quality_gate import run_quality_gate, quality_report_to_dict

    report = run_quality_gate(text, doc_type="proposal", rfp_keywords=[...])
    result_dict = quality_report_to_dict(report)
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QualityDimension:
    name: str           # e.g., "evidence_density"
    label: str          # Korean display label
    score: float        # 0.0 ~ 1.0
    max_score: float = 1.0
    status: str = ""    # pass / warn / fail
    details: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.status:
            if self.score >= 0.8:
                self.status = "pass"
            elif self.score >= 0.5:
                self.status = "warn"
            else:
                self.status = "fail"


@dataclass
class QualityReport:
    doc_type: str
    overall_score: float  # 0~100
    grade: str = ""       # 수/우/미/양/가
    dimensions: list[QualityDimension] = field(default_factory=list)
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    recommendation: str = ""

    def __post_init__(self):
        self.pass_count = sum(1 for d in self.dimensions if d.status == "pass")
        self.warn_count = sum(1 for d in self.dimensions if d.status == "warn")
        self.fail_count = sum(1 for d in self.dimensions if d.status == "fail")
        if self.overall_score >= 90:
            self.grade = "수"
        elif self.overall_score >= 80:
            self.grade = "우"
        elif self.overall_score >= 70:
            self.grade = "미"
        elif self.overall_score >= 60:
            self.grade = "양"
        else:
            self.grade = "가"


def check_evidence_density(text: str) -> QualityDimension:
    """Check density of quantitative evidence (numbers, percentages, dates)."""
    evidence_patterns = [
        r'\d+[%건명억만회개월년일]',  # Korean number+unit
        r'\d{4}년',                   # Year
        r'\d+\.\d+',                  # Decimal numbers
        r'\d+,\d{3}',                 # Formatted numbers
    ]
    total_evidence = 0
    for pattern in evidence_patterns:
        total_evidence += len(re.findall(pattern, text))

    chars = max(len(text), 1)
    density = total_evidence / (chars / 1000)  # evidence per 1000 chars

    # Target: 5+ evidence markers per 1000 chars
    score = min(density / 5.0, 1.0)
    details = [f"근거/수치 {total_evidence}건 (밀도: {density:.1f}/1000자)"]
    if density < 3:
        details.append("정량적 근거가 부족합니다. 수치, 날짜, 실적을 추가하세요.")

    return QualityDimension(
        name="evidence_density",
        label="근거/수치 밀도",
        score=score,
        details=details,
    )


def check_rfp_alignment(text: str, rfp_keywords: list[str]) -> QualityDimension:
    """Check how well the text aligns with RFP evaluation keywords."""
    if not rfp_keywords:
        return QualityDimension(
            name="rfp_alignment", label="RFP 정렬", score=1.0,
            details=["키워드 없음 — 검사 생략"],
        )

    found = 0
    missing = []
    for kw in rfp_keywords:
        if kw in text:
            found += 1
        else:
            missing.append(kw)

    score = found / max(len(rfp_keywords), 1)
    details = [f"RFP 키워드 {found}/{len(rfp_keywords)} 반영"]
    if missing:
        details.append(f"누락 키워드: {', '.join(missing[:5])}")

    return QualityDimension(
        name="rfp_alignment", label="RFP 정렬", score=score, details=details,
    )


def check_vague_expressions(text: str) -> QualityDimension:
    """Check for vague/abstract expressions without evidence."""
    try:
        from prompts.proposal_system_v2 import UNIVERSAL_VAGUE_PATTERNS
        patterns = UNIVERSAL_VAGUE_PATTERNS
    except ImportError:
        patterns = [r"최고\s*수준", r"혁신적인", r"차별화된", r"탁월한", r"풍부한\s*경험"]

    vague_re = re.compile("|".join(patterns), re.IGNORECASE)
    matches = list(vague_re.finditer(text))

    # Check if evidence follows within 200 chars
    unsubstantiated = []
    for m in matches:
        after = text[m.end():m.end() + 200]
        has_evidence = bool(re.search(r'\d+[%건명억만회]', after))
        if not has_evidence:
            unsubstantiated.append(m.group())

    score = 1.0 - min(len(unsubstantiated) / 5.0, 1.0)  # 5+ unsubstantiated = 0
    details = []
    if unsubstantiated:
        details.append(
            f"근거 없는 추상 표현 {len(unsubstantiated)}건: "
            f"{', '.join(unsubstantiated[:3])}"
        )
    else:
        details.append("금지 표현 없음")

    return QualityDimension(
        name="vague_expressions", label="금지 표현", score=score, details=details,
    )


def check_format_completeness(text: str) -> QualityDimension:
    """Check structural completeness (headings, sections, tables)."""
    has_h2 = bool(re.search(r'^##\s', text, re.MULTILINE))
    has_h3 = bool(re.search(r'^###\s', text, re.MULTILINE))
    has_table = bool(re.search(r'\|.*\|.*\|', text))
    has_list = bool(re.search(r'^[-*]\s', text, re.MULTILINE))
    has_bold = bool(re.search(r'\*\*.*\*\*', text))

    elements = [has_h2, has_h3, has_table, has_list, has_bold]
    score = sum(elements) / len(elements)

    details = []
    if not has_h2:
        details.append("## 대제목 없음")
    if not has_h3:
        details.append("### 소제목 없음")
    if not has_table:
        details.append("표(table) 없음")
    if not has_list:
        details.append("목록(bullet) 없음")
    if not details:
        details.append("구조 요소 완비")

    return QualityDimension(
        name="format_completeness", label="형식 완결성", score=score, details=details,
    )


def check_style_consistency(text: str) -> QualityDimension:
    """Check Korean formal style consistency."""
    sentences = re.split(r'[.]\s', text)
    formal_endings = 0
    informal = []

    for sent in sentences:
        sent = sent.strip()
        if not sent or len(sent) < 10:
            continue
        if re.search(
            r'(습니다|입니다|됩니다|있습니다|했습니다|겠습니다)[.]?\s*$', sent,
        ):
            formal_endings += 1
        elif re.search(r'(거든요|잖아요|인데요|할 것임|하기 바람)', sent):
            informal.append(sent[:30])

    total = max(formal_endings + len(informal), 1)
    score = formal_endings / total

    details = [f"격식체 {formal_endings}건 / 전체 {total}건"]
    if informal:
        details.append(f"비격식 표현: {informal[0]}...")

    return QualityDimension(
        name="style_consistency", label="격식체 일관성", score=score, details=details,
    )


def check_length_adequacy(text: str, target_chars: int) -> QualityDimension:
    """Check if generated text meets the target length."""
    actual = len(text)
    if target_chars <= 0:
        return QualityDimension(
            name="length", label="분량 적정성", score=1.0, details=["목표 없음"],
        )

    ratio = actual / target_chars
    if ratio >= 0.8:
        score = 1.0
    elif ratio >= 0.5:
        score = 0.6
    else:
        score = 0.3

    details = [f"{actual}자 / 목표 {target_chars}자 ({ratio * 100:.0f}%)"]
    if ratio < 0.8:
        details.append(f"{target_chars - actual}자 추가 필요")

    return QualityDimension(
        name="length", label="분량 적정성", score=score, details=details,
    )


def run_quality_gate(
    text: str,
    doc_type: str = "proposal",
    rfp_keywords: list[str] | None = None,
    target_chars: int = 2000,
    company_name: str | None = None,
) -> QualityReport:
    """Run full quality gate on generated text. Returns structured report.

    Dimensions checked:
    - evidence_density: quantitative evidence per 1000 chars
    - rfp_alignment: RFP evaluation keyword coverage
    - vague_expressions: unsubstantiated abstract claims
    - format_completeness: markdown structural elements
    - style_consistency: Korean formal style (격식체)
    - length: text length vs target
    - blind_violation: company name leakage
    """
    dimensions = [
        check_evidence_density(text),
        check_rfp_alignment(text, rfp_keywords or []),
        check_vague_expressions(text),
        check_format_completeness(text),
        check_style_consistency(text),
        check_length_adequacy(text, target_chars),
    ]

    # Blind check
    if company_name and company_name in text:
        dimensions.append(QualityDimension(
            name="blind_violation",
            label="블라인드 준수",
            score=0.0,
            details=[f"회사명 '{company_name}' 노출"],
        ))
    else:
        dimensions.append(QualityDimension(
            name="blind_violation",
            label="블라인드 준수",
            score=1.0,
            details=["위반 없음"],
        ))

    # Overall score (weighted average)
    weights = {
        "evidence_density": 2.0,
        "rfp_alignment": 2.0,
        "vague_expressions": 1.5,
        "format_completeness": 1.0,
        "style_consistency": 1.0,
        "length": 1.0,
        "blind_violation": 1.5,
    }
    total_weight = sum(weights.get(d.name, 1.0) for d in dimensions)
    weighted_sum = sum(d.score * weights.get(d.name, 1.0) for d in dimensions)
    overall = (weighted_sum / total_weight) * 100

    report = QualityReport(
        doc_type=doc_type,
        overall_score=round(overall, 1),
        dimensions=dimensions,
    )

    # Recommendation
    if report.fail_count > 0:
        report.recommendation = "품질 기준 미달 — 수정 후 재생성을 권장합니다"
    elif report.warn_count > 2:
        report.recommendation = "일부 항목 개선 필요 — 검토 후 수정을 권장합니다"
    else:
        report.recommendation = "품질 기준 통과 — 제출 가능합니다"

    logger.info(
        "Quality gate [%s]: score=%.1f grade=%s (pass=%d warn=%d fail=%d)",
        doc_type, report.overall_score, report.grade,
        report.pass_count, report.warn_count, report.fail_count,
    )

    return report


def quality_report_to_dict(report: QualityReport) -> dict:
    """Convert QualityReport to JSON-serializable dict for API response."""
    return {
        "doc_type": report.doc_type,
        "overall_score": report.overall_score,
        "grade": report.grade,
        "recommendation": report.recommendation,
        "pass_count": report.pass_count,
        "warn_count": report.warn_count,
        "fail_count": report.fail_count,
        "dimensions": [
            {
                "name": d.name,
                "label": d.label,
                "score": round(d.score, 2),
                "status": d.status,
                "details": d.details,
            }
            for d in report.dimensions
        ],
    }
