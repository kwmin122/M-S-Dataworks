"""Tests for domain-dict-based schedule planning."""
import pytest
from unittest.mock import patch, MagicMock

from pack_models import DomainDict, DomainDictRole, DomainDictPhase, DomainDictMethodology
from phase2_models import WbsTask, PersonnelAllocation
from schedule_planner import plan_schedule, _build_schedule_prompt, _allocate_personnel


@pytest.fixture
def research_domain_dict():
    return DomainDict(
        domain_type="research",
        roles=[
            DomainDictRole(id="pi", name="연구책임자", grade="특급"),
            DomainDictRole(id="ra", name="연구보조원", grade="초급"),
        ],
        phases=[
            DomainDictPhase(id="design", name="연구설계"),
            DomainDictPhase(id="collect", name="자료수집"),
            DomainDictPhase(id="analyze", name="분석/해석"),
            DomainDictPhase(id="closing", name="사업종료"),
        ],
        methodologies=[
            DomainDictMethodology(id="mixed", name="혼합연구방법"),
        ],
        deliverables_common=["연구계획서", "최종연구보고서"],
    )


@pytest.fixture
def it_domain_dict():
    return DomainDict(
        domain_type="it_build",
        roles=[
            DomainDictRole(id="pm", name="PM", grade="특급", aliases=["프로젝트매니저"]),
            DomainDictRole(id="dev", name="개발자", grade="중급"),
            DomainDictRole(id="qa", name="QA엔지니어", grade="중급"),
        ],
        phases=[
            DomainDictPhase(id="plan", name="기획/요건분석"),
            DomainDictPhase(id="design", name="설계"),
            DomainDictPhase(id="dev", name="개발"),
            DomainDictPhase(id="test", name="테스트"),
            DomainDictPhase(id="deploy", name="배포/이관"),
        ],
        methodologies=[
            DomainDictMethodology(id="waterfall", name="워터폴"),
            DomainDictMethodology(id="agile", name="애자일"),
        ],
        deliverables_common=["요건정의서", "설계서", "소스코드", "테스트결과서", "운영매뉴얼"],
    )


class TestPlanSchedule:
    @patch("schedule_planner._call_llm_schedule")
    def test_generates_tasks_from_domain_dict(self, mock_llm, research_domain_dict):
        mock_llm.return_value = [
            {"phase": "연구설계", "task_name": "연구계획 수립", "start_month": 1,
             "duration_months": 2, "responsible_role": "연구책임자", "man_months": 2.0,
             "deliverables": ["연구계획서"]},
            {"phase": "자료수집", "task_name": "설문조사", "start_month": 2,
             "duration_months": 3, "responsible_role": "연구보조원", "man_months": 3.0,
             "deliverables": ["설문결과"]},
        ]
        tasks, personnel, months = plan_schedule(
            rfx_result={"title": "연구용역", "full_text": "치유농업 연구"},
            domain_dict=research_domain_dict,
            total_months=12,
        )
        assert len(tasks) >= 2
        assert all(isinstance(t, WbsTask) for t in tasks)
        assert tasks[0].responsible_role == "연구책임자"

    @patch("schedule_planner._call_llm_schedule")
    def test_allocates_personnel(self, mock_llm, research_domain_dict):
        mock_llm.return_value = [
            {"phase": "연구설계", "task_name": "계획", "start_month": 1,
             "duration_months": 2, "responsible_role": "연구책임자", "man_months": 2.0,
             "deliverables": []},
        ]
        tasks, personnel, months = plan_schedule(
            rfx_result={"title": "연구용역"},
            domain_dict=research_domain_dict,
            total_months=6,
        )
        assert len(personnel) >= 1
        assert any(p.role == "연구책임자" for p in personnel)

    @patch("schedule_planner._call_llm_schedule")
    def test_uses_domain_phases_in_prompt(self, mock_llm, research_domain_dict):
        mock_llm.return_value = []
        plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=6,
        )
        prompt = mock_llm.call_args[0][0]  # first positional arg
        assert "연구설계" in prompt
        assert "연구책임자" in prompt

    @patch("schedule_planner._call_llm_schedule")
    def test_returns_total_months(self, mock_llm, research_domain_dict):
        mock_llm.return_value = []
        _, _, months = plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=9,
        )
        assert months == 9

    @patch("schedule_planner._call_llm_schedule")
    def test_defaults_total_months_from_rfp(self, mock_llm, research_domain_dict):
        mock_llm.return_value = []
        _, _, months = plan_schedule(
            rfx_result={"title": "test", "duration_months": 18},
            domain_dict=research_domain_dict,
            total_months=0,  # triggers fallback
        )
        assert months == 18

    @patch("schedule_planner._call_llm_schedule")
    def test_skips_invalid_tasks(self, mock_llm, research_domain_dict):
        mock_llm.return_value = [
            {"phase": "연구설계", "task_name": "유효태스크", "start_month": 1,
             "duration_months": 2, "responsible_role": "연구책임자", "man_months": 2.0,
             "deliverables": []},
            {"phase": "연구설계", "task_name": "잘못된태스크", "start_month": "invalid",
             "duration_months": 2, "responsible_role": "연구책임자", "man_months": "bad",
             "deliverables": []},  # man_months 'bad' will raise ValueError
        ]
        # Should not raise; invalid task is skipped
        tasks, _, _ = plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=6,
        )
        # At least the valid task should be present
        assert any(t.task_name == "유효태스크" for t in tasks)

    @patch("schedule_planner._call_llm_schedule")
    def test_personnel_grade_from_domain_dict(self, mock_llm, research_domain_dict):
        mock_llm.return_value = [
            {"phase": "연구설계", "task_name": "계획", "start_month": 1,
             "duration_months": 3, "responsible_role": "연구책임자", "man_months": 3.0,
             "deliverables": []},
        ]
        _, personnel, _ = plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=12,
        )
        pi = next((p for p in personnel if p.role == "연구책임자"), None)
        assert pi is not None
        assert pi.grade == "특급"

    @patch("schedule_planner._call_llm_schedule")
    def test_personnel_grade_alias(self, mock_llm, it_domain_dict):
        """Role aliases should resolve to the correct grade."""
        mock_llm.return_value = [
            {"phase": "기획/요건분석", "task_name": "요건분석", "start_month": 1,
             "duration_months": 2, "responsible_role": "프로젝트매니저", "man_months": 2.0,
             "deliverables": []},
        ]
        _, personnel, _ = plan_schedule(
            rfx_result={"title": "IT시스템"},
            domain_dict=it_domain_dict,
            total_months=12,
        )
        pm = next((p for p in personnel if p.role == "프로젝트매니저"), None)
        assert pm is not None
        assert pm.grade == "특급"

    @patch("schedule_planner._call_llm_schedule")
    def test_personnel_unknown_role_defaults_to_junggeup(self, mock_llm, research_domain_dict):
        """Unknown roles not in domain_dict get default grade '중급'."""
        mock_llm.return_value = [
            {"phase": "연구설계", "task_name": "외부자문", "start_month": 1,
             "duration_months": 1, "responsible_role": "외부전문가", "man_months": 1.0,
             "deliverables": []},
        ]
        _, personnel, _ = plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=6,
        )
        unknown = next((p for p in personnel if p.role == "외부전문가"), None)
        assert unknown is not None
        assert unknown.grade == "중급"

    @patch("schedule_planner._call_llm_schedule")
    def test_monthly_allocation_length_matches_total_months(self, mock_llm, research_domain_dict):
        mock_llm.return_value = [
            {"phase": "연구설계", "task_name": "계획", "start_month": 1,
             "duration_months": 3, "responsible_role": "연구책임자", "man_months": 3.0,
             "deliverables": []},
        ]
        _, personnel, months = plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=8,
        )
        for p in personnel:
            assert len(p.monthly_allocation) == 8

    @patch("schedule_planner._call_llm_schedule")
    def test_knowledge_texts_appear_in_prompt(self, mock_llm, research_domain_dict):
        mock_llm.return_value = []
        plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=6,
            knowledge_texts=["공공조달 WBS 핵심원칙: 단계별 산출물 명시"],
        )
        prompt = mock_llm.call_args[0][0]
        assert "공공조달 WBS 핵심원칙" in prompt

    @patch("schedule_planner._call_llm_schedule")
    def test_company_context_in_prompt(self, mock_llm, research_domain_dict):
        mock_llm.return_value = []
        plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=6,
            company_context="당사는 농업연구 10년 경력 보유",
        )
        prompt = mock_llm.call_args[0][0]
        assert "농업연구 10년 경력" in prompt

    @patch("schedule_planner._call_llm_schedule")
    def test_llm_returns_tasks_in_wrapper_key(self, mock_llm, research_domain_dict):
        """LLM sometimes wraps array in {"tasks": [...]}. Should unwrap correctly."""
        # _call_llm_schedule already handles this, but test plan_schedule end-to-end
        mock_llm.return_value = [
            {"phase": "분석/해석", "task_name": "데이터분석", "start_month": 4,
             "duration_months": 2, "responsible_role": "연구책임자", "man_months": 2.0,
             "deliverables": ["분석보고서"]},
        ]
        tasks, _, _ = plan_schedule(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=12,
        )
        assert any(t.phase == "분석/해석" for t in tasks)

    @patch("schedule_planner._call_llm_schedule")
    def test_multiple_roles_personnel_sorted_by_man_months(self, mock_llm, it_domain_dict):
        mock_llm.return_value = [
            {"phase": "개발", "task_name": "백엔드 개발", "start_month": 3,
             "duration_months": 4, "responsible_role": "개발자", "man_months": 8.0,
             "deliverables": ["소스코드"]},
            {"phase": "기획/요건분석", "task_name": "PM 킥오프", "start_month": 1,
             "duration_months": 1, "responsible_role": "PM", "man_months": 1.0,
             "deliverables": []},
            {"phase": "테스트", "task_name": "QA 검증", "start_month": 7,
             "duration_months": 2, "responsible_role": "QA엔지니어", "man_months": 2.0,
             "deliverables": ["테스트결과서"]},
        ]
        _, personnel, _ = plan_schedule(
            rfx_result={"title": "IT시스템 구축"},
            domain_dict=it_domain_dict,
            total_months=9,
        )
        # Personnel should be sorted descending by total_man_months
        totals = [p.total_man_months for p in personnel]
        assert totals == sorted(totals, reverse=True)


class TestBuildSchedulePrompt:
    def test_prompt_contains_domain_type(self, research_domain_dict):
        prompt = _build_schedule_prompt(
            rfx_result={"title": "연구용역"},
            domain_dict=research_domain_dict,
            total_months=12,
        )
        assert "research" in prompt

    def test_prompt_contains_all_phases(self, research_domain_dict):
        prompt = _build_schedule_prompt(
            rfx_result={"title": "연구용역"},
            domain_dict=research_domain_dict,
            total_months=12,
        )
        for phase in ["연구설계", "자료수집", "분석/해석", "사업종료"]:
            assert phase in prompt

    def test_prompt_contains_all_roles(self, research_domain_dict):
        prompt = _build_schedule_prompt(
            rfx_result={"title": "연구용역"},
            domain_dict=research_domain_dict,
            total_months=12,
        )
        assert "연구책임자" in prompt
        assert "연구보조원" in prompt

    def test_prompt_uses_raw_text_fallback(self, research_domain_dict):
        prompt = _build_schedule_prompt(
            rfx_result={"title": "test", "raw_text": "RAW TEXT CONTENT"},
            domain_dict=research_domain_dict,
            total_months=6,
        )
        assert "RAW TEXT CONTENT" in prompt

    def test_prompt_limits_rfp_text_to_3000_chars(self, research_domain_dict):
        long_text = "A" * 5000
        prompt = _build_schedule_prompt(
            rfx_result={"title": "test", "full_text": long_text},
            domain_dict=research_domain_dict,
            total_months=6,
        )
        # Should not contain more than 3000 A chars in a row
        assert "A" * 3001 not in prompt

    def test_prompt_includes_methodology(self, research_domain_dict):
        prompt = _build_schedule_prompt(
            rfx_result={"title": "test"},
            domain_dict=research_domain_dict,
            total_months=6,
        )
        assert "혼합연구방법" in prompt


class TestAllocatePersonnel:
    def _make_domain(self):
        return DomainDict(
            domain_type="it_build",
            roles=[
                DomainDictRole(id="pm", name="PM", grade="특급"),
                DomainDictRole(id="dev", name="개발자", grade="중급"),
            ],
        )

    def test_basic_allocation(self):
        domain = self._make_domain()
        tasks = [
            WbsTask(phase="설계", task_name="설계", start_month=1,
                    duration_months=2, responsible_role="PM", man_months=2.0),
        ]
        personnel = _allocate_personnel(tasks, total_months=6, domain_dict=domain)
        assert len(personnel) == 1
        assert personnel[0].role == "PM"
        assert personnel[0].total_man_months == 2.0
        assert len(personnel[0].monthly_allocation) == 6

    def test_aggregate_same_role(self):
        domain = self._make_domain()
        tasks = [
            WbsTask(phase="설계", task_name="설계1", start_month=1,
                    duration_months=1, responsible_role="개발자", man_months=1.0),
            WbsTask(phase="개발", task_name="개발1", start_month=2,
                    duration_months=2, responsible_role="개발자", man_months=2.0),
        ]
        personnel = _allocate_personnel(tasks, total_months=6, domain_dict=domain)
        dev = next(p for p in personnel if p.role == "개발자")
        assert dev.total_man_months == 3.0
