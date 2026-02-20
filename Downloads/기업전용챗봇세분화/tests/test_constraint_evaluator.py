"""
ConstraintEvaluator 단위 테스트.
TDD: 경계값 / SKIP / 집계 규칙 검증.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from rfx_analyzer import RFxConstraint


# ConstraintEvaluator import는 matcher.py에 구현 후 테스트
def get_evaluator():
    from matcher import ConstraintEvaluator, CompanyFactNormalizer, DeterministicComparator
    return ConstraintEvaluator(), CompanyFactNormalizer(), DeterministicComparator()


# ────────────────────────────────────────────────────────────
# 경계값 비교 테스트
# ────────────────────────────────────────────────────────────

def test_amount_exactly_at_boundary_is_pass():
    """건당 20억 == 20억 → PASS (경계 포함)"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="contract_amount", op=">=", value=20.0, unit="KRW_100M", raw="건당 20억원 이상")
    context = "KEPCO 스마트그리드 사업, 계약금액 20억원, 2023년 완료"
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "PASS", f"경계값 PASS 기대, 실제: {results[0]}"


def test_amount_below_boundary_is_fail():
    """건당 19.8억 < 20억 기준 → FAIL"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="contract_amount", op=">=", value=20.0, unit="KRW_100M", raw="건당 20억원 이상")
    context = "KEPCO 스마트그리드 사업, 계약금액 19.8억원, 2023년 완료"
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "FAIL", f"FAIL 기대, 실제: {results[0]}"
    assert results[0].observed_value is not None


def test_headcount_exactly_at_boundary():
    """정보처리기사 10명 기준, 회사 10명 → PASS"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="headcount", op=">=", value=10, unit="headcount", raw="10명 이상")
    context = "정보처리기사 자격증 보유자 10명"
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "PASS"


def test_headcount_one_below_boundary():
    """9명 < 10명 기준 → FAIL"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="headcount", op=">=", value=10, unit="headcount", raw="10명 이상")
    context = "정보처리기사 9명 보유"
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "FAIL"


# ────────────────────────────────────────────────────────────
# SKIP 케이스
# ────────────────────────────────────────────────────────────

def test_custom_metric_always_skip():
    """CUSTOM metric → 항상 SKIP"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="CUSTOM", op=">=", value=1, unit="", raw="독특한 조건")
    results = evaluator.evaluate([c], "아무 컨텍스트")
    assert results[0].outcome == "SKIP"


def test_ambiguous_period_is_skip():
    """모호한 기간 표현 → 파싱 실패 → SKIP (또는 숫자 찾으면 PASS)"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="period_years", op="<=", value=3, unit="year", raw="최근 3년간")
    context = "약 3년 전후에 수행한 사업"  # "약" 때문에 모호
    results = evaluator.evaluate([c], context)
    # period_years 파싱 불가 시 SKIP, 숫자를 찾으면 PASS도 허용
    assert results[0].outcome in ("SKIP", "PASS")


def test_completion_conflict_is_skip():
    """완료 + 진행중 동시 → SKIP"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="completion_required", op="==", value=True, unit="", raw="완료된 실적만")
    context = "KEPCO 사업 완료, 다른 사업 진행 중"  # 충돌
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "SKIP"


def test_no_info_in_context_is_skip():
    """컨텍스트에 금액 정보 없음 → SKIP"""
    evaluator, _, _ = get_evaluator()
    c = RFxConstraint(metric="contract_amount", op=">=", value=20.0, unit="KRW_100M", raw="20억 이상")
    context = "회사 설립연도 2010년, ISO 9001 인증 보유"  # 금액 정보 없음
    results = evaluator.evaluate([c], context)
    assert results[0].outcome == "SKIP"


# ────────────────────────────────────────────────────────────
# 집계 규칙 테스트
# ────────────────────────────────────────────────────────────

def test_aggregate_empty_is_fallback():
    """constraints=[] → FALLBACK_NEEDED"""
    from matcher import ConstraintEvaluator
    assert ConstraintEvaluator.aggregate([]) == "FALLBACK_NEEDED"


def test_aggregate_all_pass_is_determined_met():
    """전부 PASS → DETERMINED_MET"""
    from matcher import ConstraintEvaluator, ConstraintEvalResult
    results = [ConstraintEvalResult("PASS"), ConstraintEvalResult("PASS")]
    assert ConstraintEvaluator.aggregate(results) == "DETERMINED_MET"


def test_aggregate_any_fail_is_determined_not_met():
    """FAIL 1개 이상 → DETERMINED_NOT_MET (PASS 있어도)"""
    from matcher import ConstraintEvaluator, ConstraintEvalResult
    results = [ConstraintEvalResult("PASS"), ConstraintEvalResult("FAIL")]
    assert ConstraintEvaluator.aggregate(results) == "DETERMINED_NOT_MET"


def test_aggregate_skip_no_fail_is_fallback():
    """SKIP 포함 + FAIL 없음 → FALLBACK_NEEDED"""
    from matcher import ConstraintEvaluator, ConstraintEvalResult
    results = [ConstraintEvalResult("PASS"), ConstraintEvalResult("SKIP")]
    assert ConstraintEvaluator.aggregate(results) == "FALLBACK_NEEDED"
