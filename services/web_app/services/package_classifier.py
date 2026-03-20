"""Package Classifier — analysis snapshot → procurement domain + required package items.

Classifies bid projects into:
- Procurement domain: service (용역), goods (물품), construction (공사)
- Contract method: negotiated (협상), pq (적격심사), adequacy (적정가격), lowest_price (최저가)

Then generates the required submission package items for each (domain, method) pair.

Strategy: rule-based keyword scoring first, LLM fallback if ambiguous.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# --- Classification result ---

@dataclass
class ClassificationResult:
    procurement_domain: str  # service | goods | construction
    contract_method: str  # negotiated | pq | adequacy | lowest_price
    confidence: float  # 0.0~1.0
    detection_method: str  # rule | llm
    review_required: bool = False  # True when confidence is low or signals are ambiguous
    matched_signals: list[str] = field(default_factory=list)  # which keywords/rules matched
    warnings: list[str] = field(default_factory=list)  # operational warnings


@dataclass
class PackageItemSpec:
    """Spec for a single required submission item."""
    package_category: str  # generated_document | evidence | administrative | price
    document_code: str
    document_label: str
    required: bool = True
    generation_target: str | None = None  # doc_type for generated items
    sort_order: int = 0


# --- Keyword scoring for procurement domain ---

_DOMAIN_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "service": [
        ("용역", 5), ("정보화", 3), ("시스템 구축", 3), ("SW 개발", 3),
        ("소프트웨어", 2), ("컨설팅", 3), ("연구", 2), ("설계", 2),
        ("운영", 2), ("유지보수", 2), ("위탁", 2), ("대행", 2),
        ("개발", 2), ("기획", 2), ("분석", 1), ("감리", 3),
        ("ISP", 2), ("PMO", 2), ("교육", 2), ("조사", 2),
        ("정보통신", 3), ("CCTV", 2), ("솔루션", 2), ("플랫폼", 2),
    ],
    "goods": [
        ("물품", 5), ("납품", 4), ("구매", 4), ("조달", 3),
        ("장비", 3), ("기자재", 3), ("제조", 3), ("공급", 3),
        ("설치", 2), ("하드웨어", 3), ("서버", 2), ("네트워크", 2),
        ("라이선스", 3), ("규격", 3), ("카탈로그", 3), ("수량", 2),
        ("단가", 3), ("사양", 2), ("시험성적서", 3),
    ],
    "construction": [
        ("공사", 5), ("시공", 5), ("건설", 4), ("건축", 4),
        ("토목", 4), ("전기", 2), ("통신", 2), ("설비", 3),
        ("철거", 3), ("리모델링", 3), ("증축", 3), ("보수공사", 3),
        ("배관", 3), ("조경", 3), ("포장", 2), ("기초", 2),
        ("면허", 3), ("시공능력", 4), ("안전관리", 2),
    ],
}

_METHOD_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "negotiated": [
        ("협상에 의한", 5), ("협상계약", 5), ("기술평가", 3),
        ("기술능력평가", 3), ("배점한도", 2), ("기술점수", 2),
        ("제안서 평가", 3), ("제안요청", 2), ("기술제안서", 3),
    ],
    "pq": [
        ("적격심사", 5), ("적격", 3), ("PQ", 4),
        ("사전심사", 3), ("자격심사", 3), ("실적확인", 2),
    ],
    "adequacy": [
        ("적정가격", 4), ("적정성심사", 4), ("2단계", 3),
        ("가격적정성", 3),
    ],
    "lowest_price": [
        ("최저가", 5), ("최저가격", 4), ("최저가낙찰", 4),
        ("가격입찰", 3),
    ],
}


# --- 수의계약/견적 detection (must run before method scoring) ---

_PRIVATE_CONTRACT_KEYWORDS: list[str] = [
    "수의계약", "수의시담", "수의견적", "견적제출", "전자견적",
    "소액수의", "1인 견적", "2인 이상 견적", "견적에 의한",
    "견적서 제출", "견적 제출",
]


def _is_private_contract(text: str) -> bool:
    """Detect if the bid is a 수의계약/견적 type (not negotiated)."""
    text_lower = text.lower()
    count = sum(1 for kw in _PRIVATE_CONTRACT_KEYWORDS if kw in text_lower)
    return count >= 1


# --- Presentation evidence gate ---

_PRESENTATION_EVIDENCE_KEYWORDS: list[str] = [
    "발표평가", "제안발표", "발표자료", "프레젠테이션",
    "PT 평가", "PT평가", "발표 시간", "발표시간",
    "발표 순서", "발표순서", "발표장", "발표심사",
]


def _has_presentation_evidence(text: str) -> bool:
    """Check if bid explicitly requires presentation/발표평가."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in _PRESENTATION_EVIDENCE_KEYWORDS)


def _score_keywords(text: str, keywords: dict[str, list[tuple[str, int]]]) -> dict[str, int]:
    """Score text against keyword groups."""
    scores: dict[str, int] = {k: 0 for k in keywords}
    text_lower = text.lower()
    for category, kw_list in keywords.items():
        for kw, weight in kw_list:
            if kw.lower() in text_lower:
                scores[category] += weight
    return scores


def _best_with_threshold(scores: dict[str, int], threshold: int = 3) -> tuple[str, int]:
    """Return (best_key, best_score). Returns ('', 0) if all below threshold."""
    if not scores:
        return ("", 0)
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    score = scores[best]
    if score < threshold:
        return ("", 0)
    return (best, score)


# --- Classification ---

def classify_procurement(
    analysis_json: dict[str, Any],
    summary_md: str | None = None,
) -> ClassificationResult:
    """Classify procurement domain and contract method from analysis data.

    Uses keyword scoring on title + requirements + evaluation_criteria + summary_md.
    Returns ClassificationResult with domain, method, confidence, detection_method.
    """
    # Build text corpus from analysis fields
    parts: list[str] = []

    title = analysis_json.get("title", "")
    if title:
        # Title gets extra weight by repeating
        parts.extend([title, title])

    for req in analysis_json.get("requirements", []):
        desc = req.get("description", "")
        cat = req.get("category", "")
        if desc:
            parts.append(desc)
        if cat:
            parts.append(cat)

    for crit in analysis_json.get("evaluation_criteria", []):
        desc = crit.get("description", "")
        cat = crit.get("category", "")
        if desc:
            parts.append(desc)
        if cat:
            parts.append(cat)

    if summary_md:
        parts.append(summary_md)

    text = "\n".join(parts)

    text_lower = text.lower()
    is_private = _is_private_contract(text)

    # Domain scoring
    domain_scores = _score_keywords(text, _DOMAIN_KEYWORDS)
    best_domain, domain_score = _best_with_threshold(domain_scores, threshold=3)

    if not best_domain:
        best_domain = "service"
        domain_score = 0

    # Method scoring — 수의계약/견적 우선 분기
    method_score = 0
    if is_private:
        best_method = "pq"
        method_score = 5
        logger.info("Private contract/quotation detected → classified as pq (not negotiated)")
    else:
        method_scores = _score_keywords(text, _METHOD_KEYWORDS)
        best_method, method_score = _best_with_threshold(method_scores, threshold=3)

        if not best_method:
            best_method = "negotiated"

    # Confidence: domain margin + method score penalty
    all_domain_scores = sorted(domain_scores.values(), reverse=True)
    margin = (all_domain_scores[0] - all_domain_scores[1]) if len(all_domain_scores) > 1 else all_domain_scores[0]
    confidence = min(1.0, 0.5 + margin * 0.05)
    # Penalize confidence when method score is weak (not private contract)
    if not is_private and method_score < 3:
        confidence = min(confidence, 0.6)

    # Build matched_signals
    matched_signals: list[str] = []
    for kw, _ in _DOMAIN_KEYWORDS.get(best_domain, []):
        if kw.lower() in text_lower:
            matched_signals.append(f"domain:{kw}")
    if is_private:
        matched_signals.append("guard:수의계약/견적")
    else:
        for kw, _ in _METHOD_KEYWORDS.get(best_method, []):
            if kw.lower() in text_lower:
                matched_signals.append(f"method:{kw}")

    # Warnings (user-facing Korean)
    warnings: list[str] = []
    if domain_score < 5:
        warnings.append("사업유형(용역/물품/공사) 판단 근거 부족")
    if not is_private and method_score < 5:
        warnings.append("계약방식(협상/적격/최저가) 판단 근거 부족")

    # Review required: low confidence
    review_required = confidence < 0.65

    return ClassificationResult(
        procurement_domain=best_domain,
        contract_method=best_method,
        confidence=round(confidence, 2),
        detection_method="rule",
        review_required=review_required,
        matched_signals=matched_signals,
        warnings=warnings,
    )


# --- Package item templates ---

# Each template: (domain, method) → list of PackageItemSpec
# These define the standard submission packages for Korean public procurement.

_COMMON_EVIDENCE: list[PackageItemSpec] = [
    PackageItemSpec("evidence", "business_license", "사업자등록증", sort_order=100),
    PackageItemSpec("evidence", "tax_cert", "납세증명서", sort_order=101),
    PackageItemSpec("evidence", "financial_stmt", "재무제표", sort_order=102),
]

_COMMON_ADMIN: list[PackageItemSpec] = [
    PackageItemSpec("administrative", "bid_letter", "입찰서", sort_order=200),
    PackageItemSpec("administrative", "integrity_pledge", "청렴서약서", sort_order=201),
]

_SERVICE_NEGOTIATED: list[PackageItemSpec] = [
    # Generated documents
    PackageItemSpec("generated_document", "proposal", "기술 제안서", generation_target="proposal", sort_order=1),
    PackageItemSpec("generated_document", "execution_plan", "수행계획서/WBS", generation_target="execution_plan", sort_order=2),
    PackageItemSpec("generated_document", "presentation", "발표자료(PPT)", generation_target="presentation", sort_order=3),
    PackageItemSpec("generated_document", "track_record_doc", "실적기술서", generation_target="track_record", sort_order=4),
    # Evidence
    PackageItemSpec("evidence", "experience_cert", "용역수행실적확인서", sort_order=10),
    PackageItemSpec("evidence", "personnel_cert", "기술인력 자격증/경력증명서", sort_order=11),
    PackageItemSpec("evidence", "license_cert", "사업자 면허/등록증", sort_order=12),
    PackageItemSpec("evidence", "certification_cert", "인증서(ISO, ISMS 등)", sort_order=13),
    # Price
    PackageItemSpec("price", "price_proposal", "가격제안서", sort_order=50),
    PackageItemSpec("price", "cost_breakdown", "원가산출내역서", sort_order=51),
]

_SERVICE_PQ: list[PackageItemSpec] = [
    PackageItemSpec("generated_document", "proposal", "기술 제안서", generation_target="proposal", sort_order=1),
    PackageItemSpec("generated_document", "track_record_doc", "실적기술서", generation_target="track_record", sort_order=2),
    # PQ-specific evidence
    PackageItemSpec("evidence", "experience_cert", "용역수행실적확인서", sort_order=10),
    PackageItemSpec("evidence", "pq_personnel", "기술인력 보유 증빙", sort_order=11),
    PackageItemSpec("evidence", "license_cert", "사업자 면허/등록증", sort_order=12),
    # Price
    PackageItemSpec("price", "price_bid", "입찰가격", sort_order=50),
]

_GOODS_SPEC_PRICE: list[PackageItemSpec] = [
    PackageItemSpec("generated_document", "spec_proposal", "규격제안서/사양서", generation_target="proposal", sort_order=1),
    PackageItemSpec("generated_document", "presentation", "발표자료(PPT)", generation_target="presentation", sort_order=2),
    # Evidence
    PackageItemSpec("evidence", "catalog", "제품 카탈로그/브로슈어", sort_order=10),
    PackageItemSpec("evidence", "test_report", "시험성적서/인증서", sort_order=11),
    PackageItemSpec("evidence", "supply_record", "납품실적증명서", sort_order=12),
    PackageItemSpec("evidence", "compliance_doc", "규격적합확인서", sort_order=13),
    # Price
    PackageItemSpec("price", "unit_price", "단가산출서", sort_order=50),
    PackageItemSpec("price", "price_bid", "입찰가격", sort_order=51),
]

_GOODS_NEGOTIATED: list[PackageItemSpec] = [
    PackageItemSpec("generated_document", "proposal", "기술 제안서", generation_target="proposal", sort_order=1),
    PackageItemSpec("generated_document", "presentation", "발표자료(PPT)", generation_target="presentation", sort_order=2),
    PackageItemSpec("evidence", "catalog", "제품 카탈로그", sort_order=10),
    PackageItemSpec("evidence", "test_report", "시험성적서", sort_order=11),
    PackageItemSpec("evidence", "supply_record", "납품실적증명서", sort_order=12),
    PackageItemSpec("price", "price_proposal", "가격제안서", sort_order=50),
    PackageItemSpec("price", "cost_breakdown", "원가산출내역서", sort_order=51),
]

_CONSTRUCTION_PQ: list[PackageItemSpec] = [
    PackageItemSpec("generated_document", "proposal", "기술 제안서", generation_target="proposal", sort_order=1),
    PackageItemSpec("generated_document", "execution_plan", "시공계획서", generation_target="execution_plan", sort_order=2),
    # Evidence
    PackageItemSpec("evidence", "construction_record", "시공실적확인서", sort_order=10),
    PackageItemSpec("evidence", "engineer_cert", "건설기술인 보유증빙", sort_order=11),
    PackageItemSpec("evidence", "equipment_cert", "장비 보유 증빙", sort_order=12),
    PackageItemSpec("evidence", "license_cert", "건설업 면허증", sort_order=13),
    # Price
    PackageItemSpec("price", "price_bid", "입찰가격", sort_order=50),
    PackageItemSpec("price", "cost_estimate", "공사원가계산서", sort_order=51),
]

_CONSTRUCTION_NEGOTIATED: list[PackageItemSpec] = [
    PackageItemSpec("generated_document", "proposal", "기술 제안서", generation_target="proposal", sort_order=1),
    PackageItemSpec("generated_document", "execution_plan", "시공계획서", generation_target="execution_plan", sort_order=2),
    PackageItemSpec("generated_document", "presentation", "발표자료(PPT)", generation_target="presentation", sort_order=3),
    PackageItemSpec("evidence", "construction_record", "시공실적확인서", sort_order=10),
    PackageItemSpec("evidence", "engineer_cert", "건설기술인 증빙", sort_order=11),
    PackageItemSpec("evidence", "license_cert", "건설업 면허증", sort_order=12),
    PackageItemSpec("price", "price_proposal", "가격제안서", sort_order=50),
    PackageItemSpec("price", "cost_estimate", "공사원가계산서", sort_order=51),
]

# Lookup table: (domain, method) → items
_PACKAGE_TEMPLATES: dict[tuple[str, str], list[PackageItemSpec]] = {
    ("service", "negotiated"): _SERVICE_NEGOTIATED,
    ("service", "pq"): _SERVICE_PQ,
    ("service", "adequacy"): _SERVICE_PQ,  # similar to PQ
    ("service", "lowest_price"): _SERVICE_PQ,
    ("goods", "negotiated"): _GOODS_NEGOTIATED,
    ("goods", "pq"): _GOODS_SPEC_PRICE,
    ("goods", "adequacy"): _GOODS_SPEC_PRICE,
    ("goods", "lowest_price"): _GOODS_SPEC_PRICE,
    ("construction", "negotiated"): _CONSTRUCTION_NEGOTIATED,
    ("construction", "pq"): _CONSTRUCTION_PQ,
    ("construction", "adequacy"): _CONSTRUCTION_PQ,
    ("construction", "lowest_price"): _CONSTRUCTION_PQ,
}


def build_package_items(
    classification: ClassificationResult,
    text: str = "",
) -> list[PackageItemSpec]:
    """Build the required submission package items for a classified project.

    Returns domain-specific items + common evidence + common admin items.
    Applies presentation evidence gate: presentation only included when
    explicit 발표평가/발표자료 evidence exists in the text.
    """
    key = (classification.procurement_domain, classification.contract_method)
    domain_items = _PACKAGE_TEMPLATES.get(key, _SERVICE_NEGOTIATED)

    # Presentation evidence gate: strip presentation if no evidence
    has_pres = _has_presentation_evidence(text) if text else False
    if not has_pres:
        domain_items = [i for i in domain_items if i.generation_target != "presentation"]

    # Merge: domain-specific + common evidence + common admin
    # Avoid duplicate document_codes
    seen_codes: set[str] = set()
    result: list[PackageItemSpec] = []

    for item in domain_items:
        if item.document_code not in seen_codes:
            result.append(item)
            seen_codes.add(item.document_code)

    for item in _COMMON_EVIDENCE:
        if item.document_code not in seen_codes:
            result.append(item)
            seen_codes.add(item.document_code)

    for item in _COMMON_ADMIN:
        if item.document_code not in seen_codes:
            result.append(item)
            seen_codes.add(item.document_code)

    return sorted(result, key=lambda x: x.sort_order)


def classify_and_build(
    analysis_json: dict[str, Any],
    summary_md: str | None = None,
) -> tuple[ClassificationResult, list[PackageItemSpec]]:
    """End-to-end: classify procurement type and build package items."""
    classification = classify_procurement(analysis_json, summary_md)
    # Build text corpus for presentation evidence gate
    text_parts: list[str] = [analysis_json.get("title", "")]
    for req in analysis_json.get("requirements", []):
        text_parts.append(req.get("description", ""))
    for crit in analysis_json.get("evaluation_criteria", []):
        text_parts.append(crit.get("description", ""))
    if summary_md:
        text_parts.append(summary_md)
    full_text = "\n".join(text_parts)
    items = build_package_items(classification, text=full_text)

    logger.info(
        "Package classified: domain=%s method=%s confidence=%.2f items=%d",
        classification.procurement_domain,
        classification.contract_method,
        classification.confidence,
        len(items),
    )

    return classification, items
