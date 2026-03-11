"""Tests for Pack-aware quality checks."""
import pytest
from quality_checker import check_quality_with_pack, QualityIssue


def test_must_include_facts_pass():
    text = "발주기관 KOICA에서 추진하는 사업명 치유농업 연구의 사업목적은 정책 수립이다."
    issues = check_quality_with_pack(text, must_include_facts=["발주기관", "사업명", "사업목적"])
    missing = [i for i in issues if i.category == "missing_fact"]
    assert len(missing) == 0


def test_must_include_facts_fail():
    text = "본 사업은 치유농업 연구를 수행합니다."
    issues = check_quality_with_pack(text, must_include_facts=["발주기관명", "예산규모"])
    missing = [i for i in issues if i.category == "missing_fact"]
    assert len(missing) >= 1
    assert any("예산규모" in i.detail for i in missing)


def test_forbidden_patterns_detected():
    text = "본 사업은 최적화된 방법론으로 추진할 것임"
    issues = check_quality_with_pack(text, forbidden_patterns=[r"할 것임$", r"최적화된"])
    forbidden = [i for i in issues if i.category == "forbidden_pattern"]
    assert len(forbidden) >= 1


def test_min_chars_violation():
    text = "짧은 텍스트."
    issues = check_quality_with_pack(text, min_chars=500)
    length_issues = [i for i in issues if i.category == "length_violation"]
    assert len(length_issues) == 1


def test_combined_with_existing_checks():
    text = "M&S Solutions는 최고 수준의 역량으로 할 것임"
    issues = check_quality_with_pack(
        text,
        company_name="M&S Solutions",
        must_include_facts=["사업목적"],
        forbidden_patterns=[r"할 것임"],
    )
    categories = {i.category for i in issues}
    assert "blind_violation" in categories
    assert "missing_fact" in categories
