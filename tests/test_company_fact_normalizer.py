"""
CompanyFactNormalizer 단위 테스트.
TDD: 역방향 앵커 + 근사 수식어 모호 처리 검증.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from matcher import CompanyFactNormalizer

normalizer = CompanyFactNormalizer()


# ─────────────────────────────────────────────────────────────
# 정방향 앵커 (기존 동작 회귀 방지)
# ─────────────────────────────────────────────────────────────

def test_forward_anchor_amount_extracted():
    """keyword → N억 정방향 패턴은 정상 추출되어야 함"""
    text = "계약금액 20억원의 SI 프로젝트"
    result = normalizer._extract_amount(text)
    assert result == 20.0, f"정방향 추출 실패, 실제: {result}"


# ─────────────────────────────────────────────────────────────
# 역방향 앵커 (신규: N억 → keyword)
# ─────────────────────────────────────────────────────────────

def test_reverse_order_amount_extracted():
    """N억원 keyword (역순) 패턴도 추출되어야 함 - '20억원 규모의 계약'"""
    text = "20억원 규모의 SI 프로젝트를 수행하였음"
    result = normalizer._extract_amount(text)
    assert result == 20.0, f"역순 앵커 패턴 추출 실패, 실제: {result}"


def test_reverse_order_contract_amount_extracted():
    """'N억 계약금액' 역순 패턴 추출"""
    text = "19.8억 계약금액으로 진행된 KEPCO 사업"
    result = normalizer._extract_amount(text)
    assert result == 19.8, f"역순 계약금액 추출 실패, 실제: {result}"


# ─────────────────────────────────────────────────────────────
# 근사 수식어 → None (SKIP) - 모호 금액은 결정론적 비교 불가
# ─────────────────────────────────────────────────────────────

def test_approx_prefix_yak_returns_none():
    """'약' 수식어 앞에 붙은 금액은 모호 → None (SKIP)"""
    text = "계약금액 약 20억원 상당의 사업을 수행"
    result = normalizer._extract_amount(text)
    assert result is None, f"'약' 수식어 금액은 None이어야 함, 실제: {result}"


def test_approx_suffix_naewoi_returns_none():
    """'내외' 수식어 뒤에 오는 금액은 모호 → None (SKIP)"""
    text = "계약금액 20억원 내외의 사업"
    result = normalizer._extract_amount(text)
    assert result is None, f"'내외' 수식어 금액은 None이어야 함, 실제: {result}"


def test_approx_suffix_jeonhu_returns_none():
    """'전후' 수식어 있는 금액은 모호 → None (SKIP)"""
    text = "20억원 전후의 계약 규모"
    result = normalizer._extract_amount(text)
    assert result is None, f"'전후' 수식어 금액은 None이어야 함, 실제: {result}"


def test_approx_garyak_returns_none():
    """'가량' 수식어 있는 금액은 모호 → None (SKIP)"""
    text = "20억원 가량의 금액 규모"
    result = normalizer._extract_amount(text)
    assert result is None, f"'가량' 수식어 금액은 None이어야 함, 실제: {result}"


# ─────────────────────────────────────────────────────────────
# 복수 값 → None (기존 동작 회귀 방지)
# ─────────────────────────────────────────────────────────────

def test_conflicting_amounts_returns_none():
    """서로 다른 금액 2개가 추출되면 None (SKIP)"""
    text = "계약금액 20억원 ... 계약금액 30억원"
    result = normalizer._extract_amount(text)
    assert result is None, f"다른 금액 2개면 None이어야 함, 실제: {result}"


def test_same_amount_twice_returns_value():
    """동일 금액이 2번 나오면 그 값 반환"""
    text = "계약금액 20억원, 금액 20억원"
    result = normalizer._extract_amount(text)
    assert result == 20.0, f"동일 금액 2회면 해당 값이어야 함, 실제: {result}"
