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

    def test_keyword_in_rfp_activates_section(self):
        """keyword_in_rfp condition should activate section when keyword found in RFP text."""
        sections = [_make_section("s08", "연구윤리 및 IRB", required=False,
                                   conditions={"any_of": [
                                       {"keyword_in_rfp": ["IRB", "생명윤리", "연구윤리"]},
                                       {"keyword_in_rfp": ["설문조사", "FGI"]},
                                   ]})]
        result = resolve_sections(sections, rfp_context={"full_text": "본 연구는 IRB 심의를 거쳐 수행"})
        assert result[0].status == SectionStatus.ACTIVE

    def test_keyword_in_rfp_omits_when_no_match(self):
        """keyword_in_rfp condition should omit section when no keywords found."""
        sections = [_make_section("s08", "연구윤리 및 IRB", required=False,
                                   conditions={"any_of": [
                                       {"keyword_in_rfp": ["IRB", "생명윤리"]},
                                   ]})]
        result = resolve_sections(sections, rfp_context={"full_text": "일반 사업 내용"})
        assert result[0].status == SectionStatus.OMITTED

    def test_keyword_in_rfp_second_group_match(self):
        """any_of with multiple keyword groups — second group matches."""
        sections = [_make_section("s08", "연구윤리", required=False,
                                   conditions={"any_of": [
                                       {"keyword_in_rfp": ["IRB"]},
                                       {"keyword_in_rfp": ["설문조사", "FGI"]},
                                   ]})]
        result = resolve_sections(sections, rfp_context={"full_text": "FGI 참여자 대상 연구"})
        assert result[0].status == SectionStatus.ACTIVE

    def test_omitted_section_not_in_active_list(self):
        sections = [
            _make_section("s01", "사업 이해"),
            _make_section("s07", "리스크", required=False,
                         conditions={"any_of": [{"min_budget_krw": 999999999999}]}),
        ]
        result = resolve_sections(sections, rfp_context={"budget_krw": 1000})
        active = [r for r in result if r.status != SectionStatus.OMITTED]
        assert len(active) == 1
