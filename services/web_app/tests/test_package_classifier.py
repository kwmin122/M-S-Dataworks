"""Package classifier tests — domain/method classification + package item generation.

Tests:
1. Service negotiated RFP → proposal/presentation/execution_plan generated items
2. PQ-style project → PQ-related evidence items
3. Goods spec-price → spec/compliance artifacts
4. Construction → construction-specific evidence
5. Default fallback for ambiguous text
6. Package items have no duplicate document_codes
7. Common items (사업자등록증, 입찰서) always included
"""
from __future__ import annotations

import pytest
from services.web_app.services.package_classifier import (
    classify_procurement,
    build_package_items,
    classify_and_build,
    ClassificationResult,
)


# --- Test fixtures ---

SERVICE_NEGOTIATED_RFP = {
    "title": "2026년 XX교육청 학사행정시스템 구축 용역",
    "issuing_org": "XX교육청",
    "budget": "8억5천만원",
    "project_period": "2026-06 ~ 2027-05",
    "evaluation_criteria": [
        {"category": "기술평가", "max_score": 70, "description": "기술제안서 평가, 배점한도 70점"},
        {"category": "가격평가", "max_score": 30, "description": "가격점수"},
    ],
    "requirements": [
        {"category": "기능요건", "description": "학적관리, 성적처리, 출결관리 모듈 구축"},
        {"category": "기술요건", "description": "클라우드 네이티브 아키텍처 기반 SW 개발"},
        {"category": "실적요건", "description": "유사 정보시스템 구축 용역 수행실적"},
    ],
}

SERVICE_PQ_RFP = {
    "title": "2026년 도서관 시스템 유지보수 용역 적격심사",
    "issuing_org": "XX시청",
    "budget": "2억원",
    "evaluation_criteria": [
        {"category": "적격심사", "max_score": 100, "description": "PQ 자격심사 점수"},
    ],
    "requirements": [
        {"category": "실적요건", "description": "유사 시스템 유지보수 실적확인서"},
        {"category": "인력요건", "description": "기술인력 보유 증빙"},
    ],
}

GOODS_RFP = {
    "title": "2026년 사무용 PC 및 서버 장비 구매",
    "issuing_org": "YY공단",
    "budget": "5억원",
    "evaluation_criteria": [
        {"category": "규격심사", "max_score": 60, "description": "규격적합 확인"},
        {"category": "가격평가", "max_score": 40, "description": "단가 평가"},
    ],
    "requirements": [
        {"category": "규격요건", "description": "PC 300대, 서버 5대 납품"},
        {"category": "인증요건", "description": "시험성적서 및 카탈로그 제출"},
    ],
}

CONSTRUCTION_RFP = {
    "title": "2026년 XX청사 리모델링 공사",
    "issuing_org": "ZZ시청",
    "budget": "30억원",
    "evaluation_criteria": [
        {"category": "적격심사", "max_score": 100, "description": "시공능력, 실적 기반 PQ"},
    ],
    "requirements": [
        {"category": "면허요건", "description": "건설업 면허 보유"},
        {"category": "실적요건", "description": "유사 리모델링 시공실적"},
        {"category": "인력요건", "description": "건설기술인 보유 증빙"},
    ],
}

AMBIGUOUS_RFP = {
    "title": "2026년 업무 개선 사업",
    "issuing_org": "AA기관",
    "budget": "1억원",
    "evaluation_criteria": [],
    "requirements": [],
}


# --- Classification tests ---

def test_service_negotiated_classification():
    result = classify_procurement(SERVICE_NEGOTIATED_RFP)
    assert result.procurement_domain == "service"
    assert result.contract_method == "negotiated"
    assert result.confidence > 0.5
    assert result.detection_method == "rule"


def test_service_pq_classification():
    result = classify_procurement(SERVICE_PQ_RFP)
    assert result.procurement_domain == "service"
    assert result.contract_method == "pq"


def test_goods_classification():
    result = classify_procurement(GOODS_RFP)
    assert result.procurement_domain == "goods"


def test_construction_classification():
    result = classify_procurement(CONSTRUCTION_RFP)
    assert result.procurement_domain == "construction"


def test_ambiguous_defaults_to_service_negotiated():
    """Ambiguous text defaults to service/negotiated (most common in Korean procurement)."""
    result = classify_procurement(AMBIGUOUS_RFP)
    assert result.procurement_domain == "service"
    assert result.contract_method == "negotiated"


def test_summary_md_affects_classification():
    """summary_md is included in classification text corpus."""
    ambiguous = {"title": "사업", "requirements": [], "evaluation_criteria": []}
    result_without = classify_procurement(ambiguous)

    result_with = classify_procurement(
        ambiguous,
        summary_md="본 사업은 물품 구매 납품 사업으로 장비 설치 및 카탈로그 기반 규격 확인 후 단가 입찰",
    )
    assert result_with.procurement_domain == "goods"


# --- Package item generation tests ---

def test_service_negotiated_package_items():
    """Service negotiated with presentation evidence should have all 4 generated docs."""
    classification = ClassificationResult("service", "negotiated", 0.9, "rule")
    # With presentation evidence
    items = build_package_items(classification, text="기술제안서 및 발표평가 배점한도 70점")

    codes = {i.document_code for i in items}
    # Generated documents
    assert "proposal" in codes
    assert "execution_plan" in codes
    assert "presentation" in codes
    assert "track_record_doc" in codes
    # Evidence
    assert "experience_cert" in codes
    assert "personnel_cert" in codes
    # Common
    assert "business_license" in codes
    assert "bid_letter" in codes
    # Price
    assert "price_proposal" in codes


def test_pq_package_has_pq_evidence():
    """PQ project should have PQ-specific evidence items."""
    classification = ClassificationResult("service", "pq", 0.8, "rule")
    items = build_package_items(classification)

    codes = {i.document_code for i in items}
    assert "pq_personnel" in codes
    assert "experience_cert" in codes
    # PQ typically doesn't have presentation
    assert "presentation" not in codes


def test_goods_package_has_catalog_and_test_report():
    """Goods package should include catalog, test report, compliance doc."""
    classification = ClassificationResult("goods", "pq", 0.8, "rule")
    items = build_package_items(classification)

    codes = {i.document_code for i in items}
    assert "catalog" in codes
    assert "test_report" in codes
    assert "compliance_doc" in codes
    assert "supply_record" in codes


def test_construction_package_has_license_and_engineer():
    """Construction should have construction-specific evidence."""
    classification = ClassificationResult("construction", "pq", 0.8, "rule")
    items = build_package_items(classification)

    codes = {i.document_code for i in items}
    assert "construction_record" in codes
    assert "engineer_cert" in codes
    assert "license_cert" in codes


def test_no_duplicate_document_codes():
    """Package items must not have duplicate document_codes."""
    classification = ClassificationResult("service", "negotiated", 0.9, "rule")
    items = build_package_items(classification)

    codes = [i.document_code for i in items]
    assert len(codes) == len(set(codes)), f"Duplicate codes: {[c for c in codes if codes.count(c) > 1]}"


def test_common_items_always_included():
    """사업자등록증, 납세증명서, 입찰서 are always included."""
    for domain in ("service", "goods", "construction"):
        for method in ("negotiated", "pq"):
            classification = ClassificationResult(domain, method, 0.9, "rule")
            items = build_package_items(classification)
            codes = {i.document_code for i in items}

            assert "business_license" in codes, f"Missing business_license for {domain}/{method}"
            assert "tax_cert" in codes, f"Missing tax_cert for {domain}/{method}"
            assert "bid_letter" in codes, f"Missing bid_letter for {domain}/{method}"


def test_items_sorted_by_sort_order():
    """Items should be sorted by sort_order."""
    classification = ClassificationResult("service", "negotiated", 0.9, "rule")
    items = build_package_items(classification)

    orders = [i.sort_order for i in items]
    assert orders == sorted(orders)


def test_generated_items_have_generation_target():
    """Items with category 'generated_document' must have generation_target set."""
    classification = ClassificationResult("service", "negotiated", 0.9, "rule")
    items = build_package_items(classification)

    for item in items:
        if item.package_category == "generated_document":
            assert item.generation_target is not None, f"{item.document_code} missing generation_target"


# --- End-to-end test ---

def test_classify_and_build_e2e():
    """Full pipeline: analysis_json → classification + items."""
    classification, items = classify_and_build(SERVICE_NEGOTIATED_RFP)

    assert classification.procurement_domain == "service"
    assert classification.contract_method == "negotiated"
    assert len(items) > 0

    # Verify items have all required fields
    for item in items:
        assert item.package_category in ("generated_document", "evidence", "administrative", "price")
        assert item.document_code
        assert item.document_label


def test_classify_and_build_construction():
    classification, items = classify_and_build(CONSTRUCTION_RFP)

    assert classification.procurement_domain == "construction"
    codes = {i.document_code for i in items}
    assert "construction_record" in codes
    assert "license_cert" in codes


# --- Slice 4.5: misclassification hotfix tests ---

# Real-world fixture: 수의계약/견적 공고 (Doc A from validation)
PRIVATE_CONTRACT_QUOTATION_RFP = {
    "title": "2026년 동탄구 오수관로 흡입준설, CCTV, 송연조사, 비굴착보수 단가공사",
    "requirements": [
        {"category": "필수자격", "description": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령 제13조 및 같은 법 시행규칙 제14조의 자격을 갖추고, 건설산업기본법 제16조에 의한 전문건설업 중 상하수도설비공사업을 등록한 건설사업자"},
        {"category": "필수자격", "description": "입찰공고일 현재 하수도 준설차량과 관로조사용CCTV촬영장비를 소유한 업체"},
    ],
}

# Real-world: 감리 견적 공고 (Doc B from validation)
SUPERVISION_QUOTATION_RFP = {
    "title": "[9권역]학교 유무선 네트워크개선 3차 정보통신공사 감리용역",
    "requirements": [
        {"category": "필수자격", "description": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령제13조에 따른 요건을 갖춘 자"},
        {"category": "기타", "description": "조달청에 입찰참가자격등록을 한 자"},
    ],
}

# Real-world: 협상형 + 발표평가 명시 (Doc C from validation)
NEGOTIATED_WITH_PRESENTATION_RFP = {
    "title": "CCTV 감시 시스템 구축 및 유지보수 관리·운영",
    "requirements": [
        {"category": "필수자격", "description": "정보통신공사업자 등록"},
        {"category": "필수자격", "description": "중소기업 확인서 소지"},
    ],
    "evaluation_criteria": [
        {"category": "기술평가", "description": "기술제안서 및 발표평가 배점 70점"},
        {"category": "가격평가", "description": "가격평가 30점"},
    ],
}

# Explicit 수의계약 keywords in summary
EXPLICIT_PRIVATE_CONTRACT_SUMMARY = "본 공사는 지방자치단체 입찰 및 집행기준 제5장 수의계약 운영요령에 따라 견적제출하는 수의계약 공사입니다."
EXPLICIT_QUOTATION_SUMMARY = "견적에 의한 수의시담 견적서 제출 안내 공고"


def test_private_contract_not_negotiated():
    """수의계약/견적 공고는 negotiated가 아니어야 한다."""
    result = classify_procurement(
        PRIVATE_CONTRACT_QUOTATION_RFP,
        summary_md=EXPLICIT_PRIVATE_CONTRACT_SUMMARY,
    )
    assert result.contract_method != "negotiated", f"수의계약이 negotiated로 분류됨: {result}"


def test_quotation_supervision_not_negotiated():
    """견적제출 감리 공고는 negotiated가 아니어야 한다."""
    result = classify_procurement(
        SUPERVISION_QUOTATION_RFP,
        summary_md=EXPLICIT_QUOTATION_SUMMARY,
    )
    assert result.contract_method != "negotiated", f"견적제출이 negotiated로 분류됨: {result}"


def test_no_presentation_without_evidence():
    """발표평가 근거가 없는 공고에는 presentation이 포함되지 않아야 한다."""
    # 수의계약 공사 → presentation false positive 방지
    classification, items = classify_and_build(
        PRIVATE_CONTRACT_QUOTATION_RFP,
        summary_md=EXPLICIT_PRIVATE_CONTRACT_SUMMARY,
    )
    codes = {i.document_code for i in items}
    assert "presentation" not in codes, f"발표 근거 없는데 presentation 포함됨"


def test_negotiated_with_presentation_evidence_includes_presentation():
    """협상계약 + 발표평가 명시 공고에는 presentation이 포함되어야 한다."""
    classification, items = classify_and_build(NEGOTIATED_WITH_PRESENTATION_RFP)
    codes = {i.document_code for i in items}
    assert "presentation" in codes, f"발표평가 있는데 presentation 미포함"


def test_construction_quotation_excludes_presentation():
    """공사 견적 공고에는 presentation이 없어야 한다."""
    classification, items = classify_and_build(
        PRIVATE_CONTRACT_QUOTATION_RFP,
        summary_md=EXPLICIT_PRIVATE_CONTRACT_SUMMARY,
    )
    codes = {i.document_code for i in items}
    assert "presentation" not in codes


# Slice 4.5+ regression: "구축" false positive
def test_cctv_system_classified_as_service():
    """CCTV 감시 시스템 구축 용역은 construction이 아니라 service여야 한다.

    "정보통신공사업자"의 "공사"가 construction으로 잡히는 false positive 방지.
    """
    result = classify_procurement({
        "title": "CCTV 감시 시스템 구축 및 유지보수 관리 운영",
        "requirements": [
            {"category": "필수자격", "description": "정보통신공사업자 등록"},
            {"category": "필수자격", "description": "중소기업 확인서 소지"},
        ],
        "evaluation_criteria": [
            {"category": "기술평가", "description": "기술제안서 및 발표평가 배점 70점"},
        ],
    })
    assert result.procurement_domain == "service", f"CCTV 구축이 {result.procurement_domain}로 분류됨"


def test_real_telecom_construction_stays_construction():
    """실제 정보통신공사는 여전히 construction이어야 한다.

    "정보통신"이 service 키워드지만, "~공사"가 title에 있고
    시공능력 등 construction 신호가 강하면 construction 유지.
    """
    result = classify_procurement({
        "title": "○○청사 정보통신공사",
        "requirements": [
            {"description": "정보통신공사업 등록업체"},
            {"description": "시공능력평가액 10억 이상"},
        ],
    })
    assert result.procurement_domain == "construction"


def test_iot_service_not_construction():
    """IoT 솔루션 설치 운영은 service여야 한다."""
    result = classify_procurement({
        "title": "IoT 스마트 센서 설치 및 운영관리 용역",
        "requirements": [
            {"description": "정보통신공사업자 등록"},
            {"description": "IoT 솔루션 납품 실적"},
        ],
    })
    assert result.procurement_domain == "service"
