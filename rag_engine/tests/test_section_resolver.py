"""Tests for section condition evaluation."""
import pytest
from pack_models import PackSection, PackSubsection, GenerationTarget
from section_resolver import resolve_sections, SectionStatus


def _make_section(id, name, conditions=None, required=True, **kwargs):
    return PackSection(
        id=id, name=name, level=1, weight=0.1, max_score=10,
        required=required,
        conditions=conditions or {"always": True},
        **kwargs,
    )


class TestResolveSections:
    def test_always_active(self):
        sections = [_make_section("s01", "사업 이해")]
        result = resolve_sections(sections, rfp_context={})
        assert result[0].status == SectionStatus.ACTIVE

    def test_condition_min_budget_met(self):
        sections = [_make_section("s07", "리스크", required=False,
                                   conditions={"any_of": [{"min_budget_krw": 100000000}]})]
        result = resolve_sections(sections, rfp_context={"budget_krw": 200000000})
        assert result[0].status == SectionStatus.ACTIVE

    def test_condition_min_budget_not_met(self):
        sections = [_make_section("s07", "리스크", required=False,
                                   conditions={"any_of": [{"min_budget_krw": 100000000}]})]
        result = resolve_sections(sections, rfp_context={"budget_krw": 50000000})
        assert result[0].status == SectionStatus.OMITTED

    def test_condition_domain_types_match(self):
        sections = [_make_section("s07", "리스크", required=False,
                                   conditions={"any_of": [{"domain_types": ["it_build"]}]})]
        result = resolve_sections(sections, rfp_context={"domain_type": "it_build"})
        assert result[0].status == SectionStatus.ACTIVE

    def test_dynamic_subsection(self):
        sections = [_make_section("s03", "세부 수행", subsections=[
            PackSubsection(id="s03_auto", name="(자동)", dynamic=True),
        ])]
        rfp_tasks = ["과업1: 설문조사", "과업2: 데이터분석"]
        result = resolve_sections(sections, rfp_context={"tasks": rfp_tasks})
        assert result[0].status == SectionStatus.ACTIVE
        assert len(result[0].dynamic_subsections) == 2

    def test_omitted_section_not_in_active_list(self):
        sections = [
            _make_section("s01", "사업 이해"),
            _make_section("s07", "리스크", required=False,
                         conditions={"any_of": [{"min_budget_krw": 999999999999}]}),
        ]
        result = resolve_sections(sections, rfp_context={"budget_krw": 1000})
        active = [r for r in result if r.status != SectionStatus.OMITTED]
        assert len(active) == 1
