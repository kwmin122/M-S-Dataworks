"""Tests for wbs_planner.py."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from unittest.mock import MagicMock, patch
from phase2_models import MethodologyType
from wbs_planner import (
    _extract_project_duration,
    _detect_methodology,
    _detect_methodology_keywords,
    _detect_domain,
    _get_domain_template,
    _fallback_tasks,
    plan_wbs,
    WATERFALL_TEMPLATE,
    AGILE_TEMPLATE,
    DOMAIN_TEMPLATES,
    DOMAIN_KEYWORDS,
    ROLE_GRADES,
    _DOMAIN_DEFAULT_ROLE,
)


def _mock_llm_resp(content: str, finish_reason: str = "stop") -> MagicMock:
    """LLM mock response 생성 헬퍼. finish_reason 명시적 설정."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.choices[0].finish_reason = finish_reason
    return resp


def _rfx_result(period="8개월"):
    return {
        "title": "스마트시티 통합플랫폼 구축",
        "issuing_org": "서울시",
        "budget": "50억",
        "project_period": period,
        "requirements": [
            {"category": "기술", "description": "IoT 센서 통합"},
            {"category": "기술", "description": "실시간 모니터링 시스템"},
        ],
    }


def test_extract_project_duration_months():
    assert _extract_project_duration({"project_period": "8개월"}) == 8
    assert _extract_project_duration({"project_period": "12개월"}) == 12


def test_extract_project_duration_years():
    assert _extract_project_duration({"project_period": "1년"}) == 12
    assert _extract_project_duration({"project_period": "2년"}) == 24


def test_extract_project_duration_default():
    assert _extract_project_duration({}) == 6
    assert _extract_project_duration({"project_period": ""}) == 6


def test_detect_methodology_keywords_waterfall():
    rfx = {"title": "폭포수 방법론 기반 구축", "requirements": []}
    assert _detect_methodology_keywords(rfx) == MethodologyType.WATERFALL


def test_detect_methodology_keywords_agile():
    rfx = {"title": "애자일 스크럼 기반 개발", "requirements": []}
    assert _detect_methodology_keywords(rfx) == MethodologyType.AGILE


def test_detect_methodology_no_api_key_uses_keywords():
    """api_key 없으면 키워드 fallback 사용."""
    rfx = {"title": "스크럼 기반 개발", "requirements": []}
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
        result = _detect_methodology(rfx, api_key=None)
    assert result == MethodologyType.AGILE


def test_detect_methodology_llm_waterfall():
    """LLM이 waterfall 반환하는 경우."""
    rfx = _rfx_result()
    mock_response = _mock_llm_resp(json.dumps({
        "methodology": "waterfall",
        "confidence": 0.9,
        "reasoning": "단계별 산출물 명시, 감리 기반 사업",
    }))

    with patch("wbs_planner.call_with_retry", return_value=mock_response):
        result = _detect_methodology(rfx, api_key="test-key")
    assert result == MethodologyType.WATERFALL


def test_detect_methodology_llm_hybrid():
    """LLM이 hybrid 반환하는 경우."""
    rfx = {
        "title": "스마트시티 플랫폼 구축",
        "rfp_text_summary": "설계까지 단계별 진행, 개발은 반복적 스프린트 방식 채택",
        "requirements": [{"description": "마이크로서비스 아키텍처"}],
    }
    mock_response = _mock_llm_resp(json.dumps({
        "methodology": "hybrid",
        "confidence": 0.85,
        "reasoning": "설계 waterfall + 개발 agile 병행",
    }))

    with patch("wbs_planner.call_with_retry", return_value=mock_response):
        result = _detect_methodology(rfx, api_key="test-key")
    assert result == MethodologyType.HYBRID


def test_detect_methodology_llm_agile():
    """LLM이 agile 반환하는 경우."""
    rfx = {
        "title": "스프린트 기반 개발 사업",
        "rfp_text_summary": "애자일 방법론 적용, 2주 스프린트 반복",
        "requirements": [{"description": "MVP 단계별 릴리즈"}],
    }
    mock_response = _mock_llm_resp(json.dumps({
        "methodology": "agile",
        "confidence": 0.92,
        "reasoning": "명시적 스프린트/애자일 언급, MVP 릴리즈 요구",
    }))

    with patch("wbs_planner.call_with_retry", return_value=mock_response):
        result = _detect_methodology(rfx, api_key="test-key")
    assert result == MethodologyType.AGILE


def test_detect_methodology_llm_failure_fallback():
    """LLM 실패 시 키워드 fallback."""
    rfx = {"title": "애자일 기반 시스템 개발", "requirements": []}
    with patch("wbs_planner.call_with_retry", side_effect=Exception("API error")):
        result = _detect_methodology(rfx, api_key="test-key")
    assert result == MethodologyType.AGILE  # keyword fallback detects agile


def test_fallback_tasks_generates_tasks():
    tasks = _fallback_tasks(WATERFALL_TEMPLATE, 8)
    assert len(tasks) > 0
    # All tasks should have valid months
    for t in tasks:
        assert t.start_month >= 1
        assert t.duration_months >= 1
        assert t.man_months > 0


def test_plan_wbs_with_mock_llm():
    """Structured Outputs 형식 {tasks: [...]} 응답 처리."""
    mock_items = {
        "tasks": [
            {
                "phase": "착수",
                "task_name": "사업 착수 보고",
                "start_month": 1,
                "duration_months": 1,
                "deliverables": ["착수보고서"],
                "responsible_role": "PM",
                "man_months": 1.0,
            },
            {
                "phase": "분석",
                "task_name": "IoT 센서 요구사항 분석",
                "start_month": 2,
                "duration_months": 2,
                "deliverables": ["요구사항정의서"],
                "responsible_role": "PL",
                "man_months": 2.0,
            },
        ]
    }
    mock_response = _mock_llm_resp(json.dumps(mock_items, ensure_ascii=False))

    with patch("wbs_planner.call_with_retry", return_value=mock_response):
        tasks, personnel, months, methodology = plan_wbs(
            _rfx_result(),
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
        )
    assert len(tasks) == 2
    assert tasks[0].phase == "착수"
    assert tasks[1].task_name == "IoT 센서 요구사항 분석"  # RFP 맞춤 태스크명
    assert months == 8
    assert methodology == MethodologyType.WATERFALL
    assert len(personnel) > 0


def test_plan_wbs_with_knowledge_texts():
    """Layer 1 지식이 주입되는 경우."""
    mock_items = {
        "tasks": [
            {
                "phase": "착수",
                "task_name": "사업 착수 보고",
                "start_month": 1,
                "duration_months": 1,
                "deliverables": ["착수보고서", "사업수행계획서"],
                "responsible_role": "PM",
                "man_months": 1.0,
            },
        ]
    }
    mock_response = _mock_llm_resp(json.dumps(mock_items, ensure_ascii=False))

    knowledge = [
        "착수 단계에서 사업수행계획서 제출 필수",
        "감리 대상 사업은 감리계획서 포함",
    ]

    with patch("wbs_planner.call_with_retry", return_value=mock_response):
        tasks, personnel, months, methodology = plan_wbs(
            _rfx_result(),
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
            knowledge_texts=knowledge,
        )
    assert len(tasks) == 1
    assert "사업수행계획서" in tasks[0].deliverables


def test_plan_wbs_llm_failure_uses_fallback():
    with patch("wbs_planner.call_with_retry", side_effect=Exception("LLM down")):
        tasks, personnel, months, methodology = plan_wbs(
            _rfx_result(),
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
        )
    assert len(tasks) > 0  # fallback tasks generated
    assert months == 8


def test_plan_wbs_truncated_uses_fallback():
    """finish_reason='length' triggers template fallback."""
    mock_response = _mock_llm_resp('{"tasks": [}', finish_reason="length")

    with patch("wbs_planner.call_with_retry", return_value=mock_response):
        tasks, _, _, _ = plan_wbs(
            _rfx_result(),
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
        )
    assert len(tasks) > 0  # fallback tasks, not empty


def test_plan_wbs_no_api_key_uses_fallback():
    """API key 없으면 fallback 템플릿 사용."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
        tasks, personnel, months, methodology = plan_wbs(
            _rfx_result(),
            methodology=MethodologyType.WATERFALL,
        )
    assert len(tasks) > 0  # fallback tasks generated
    assert months == 8


# ---------------------------------------------------------------------------
# Domain detection tests
# ---------------------------------------------------------------------------

def test_detect_domain_construction():
    """건설/공사 도메인 감지."""
    assert _detect_domain("도로 건설 공사 시공 관리") == "construction"


def test_detect_domain_supervision():
    """감리 도메인 감지."""
    assert _detect_domain("정보시스템 감리 용역") == "supervision"


def test_detect_domain_consulting():
    """컨설팅 도메인 감지."""
    assert _detect_domain("ISP 정보화전략 컨설팅") == "consulting"


def test_detect_domain_research():
    """연구 도메인 감지."""
    assert _detect_domain("R&D 연구 용역 학술 실험") == "research"


def test_detect_domain_goods():
    """물품 도메인 감지."""
    assert _detect_domain("장비 기자재 납품 설치") == "goods"


def test_detect_domain_it_build():
    """IT 구축 도메인 감지."""
    assert _detect_domain("정보시스템 소프트웨어 구축 개발") == "it_build"


def test_detect_domain_default_fallback():
    """키워드 없으면 it_build 기본값."""
    assert _detect_domain("특별한 키워드 없는 사업") == "it_build"


def test_detect_domain_mixed_highest_wins():
    """여러 도메인 키워드 혼재 시 최다 매칭 도메인."""
    # construction keywords: 공사, 시공, 건설 = 3 hits
    # it_build keywords: 개발 = 1 hit
    text = "건설 공사 시공 관리 시스템 개발"
    assert _detect_domain(text) == "construction"


# ---------------------------------------------------------------------------
# Domain template selection tests
# ---------------------------------------------------------------------------

def test_get_domain_template_construction_waterfall():
    """건설 도메인 + waterfall → 건설 전용 템플릿."""
    template = _get_domain_template("construction", MethodologyType.WATERFALL)
    phase_names = [p["phase"] for p in template]
    assert "시공" in phase_names
    assert "아키텍처 설계" not in [t for p in template for t in p["tasks"]]


def test_get_domain_template_nonit_agile_fallback():
    """비-IT 도메인 + agile → IT agile 템플릿 fallback."""
    template = _get_domain_template("construction", MethodologyType.AGILE)
    # Should fall back to IT agile template
    phase_names = [p["phase"] for p in template]
    assert "스프린트 1~N" in phase_names


def test_get_domain_template_unknown_domain_fallback():
    """알 수 없는 도메인 → it_build 기본."""
    template = _get_domain_template("unknown_domain", MethodologyType.WATERFALL)
    # Falls back to it_build waterfall
    phase_names = [p["phase"] for p in template]
    assert "착수" in phase_names


# ---------------------------------------------------------------------------
# Role grade mapping tests
# ---------------------------------------------------------------------------

def test_role_grades_it():
    """IT 역할 등급 매핑."""
    assert ROLE_GRADES["PM"] == "특급"
    assert ROLE_GRADES["PL"] == "고급"
    assert ROLE_GRADES["아키텍트"] == "고급"


def test_role_grades_construction():
    """건설 역할 등급 매핑."""
    assert ROLE_GRADES["현장소장"] == "특급"
    assert ROLE_GRADES["시공관리자"] == "고급"
    assert ROLE_GRADES["안전관리자"] == "고급"


def test_role_grades_supervision():
    """감리 역할 등급 매핑."""
    assert ROLE_GRADES["총괄감리원"] == "특급"
    assert ROLE_GRADES["감리원"] == "중급"


def test_role_grades_research():
    """연구 역할 등급 매핑."""
    assert ROLE_GRADES["연구책임자"] == "특급"
    assert ROLE_GRADES["연구원"] == "중급"


def test_role_grades_consulting():
    """컨설팅 역할 등급 매핑."""
    assert ROLE_GRADES["수석컨설턴트"] == "특급"
    assert ROLE_GRADES["컨설턴트"] == "중급"


# ---------------------------------------------------------------------------
# Fallback tasks with domain
# ---------------------------------------------------------------------------

def test_fallback_tasks_construction_domain():
    """건설 도메인 fallback → 시공관리자 기본 역할."""
    template = DOMAIN_TEMPLATES["construction"]["waterfall"]
    tasks = _fallback_tasks(template, 12, domain="construction")
    assert len(tasks) > 0
    # All tasks should have construction default role
    for t in tasks:
        assert t.responsible_role == "시공관리자"
    # Should have construction phase names
    phases = {t.phase for t in tasks}
    assert "시공" in phases


def test_fallback_tasks_research_domain():
    """연구 도메인 fallback → 연구원 기본 역할."""
    template = DOMAIN_TEMPLATES["research"]["waterfall"]
    tasks = _fallback_tasks(template, 10, domain="research")
    assert len(tasks) > 0
    for t in tasks:
        assert t.responsible_role == "연구원"
    phases = {t.phase for t in tasks}
    assert "연구수행" in phases


def test_fallback_tasks_supervision_domain():
    """감리 도메인 fallback → 감리원 기본 역할."""
    template = DOMAIN_TEMPLATES["supervision"]["waterfall"]
    tasks = _fallback_tasks(template, 8, domain="supervision")
    assert len(tasks) > 0
    for t in tasks:
        assert t.responsible_role == "감리원"


def test_fallback_tasks_it_build_backward_compat():
    """기존 IT fallback 동작 유지 (domain 미지정 시 it_build 기본)."""
    tasks = _fallback_tasks(WATERFALL_TEMPLATE, 8)
    assert len(tasks) > 0
    for t in tasks:
        assert t.responsible_role == "개발자"


# ---------------------------------------------------------------------------
# plan_wbs domain integration tests
# ---------------------------------------------------------------------------

def _rfx_construction():
    return {
        "title": "OO도로 건설 공사",
        "issuing_org": "국토교통부",
        "budget": "100억",
        "project_period": "24개월",
        "requirements": [
            {"category": "공사", "description": "토공사 및 구조물 시공"},
            {"category": "안전", "description": "건설안전관리 계획"},
        ],
    }


def _rfx_research():
    return {
        "title": "차세대 AI 기술 연구 용역",
        "issuing_org": "과학기술정보통신부",
        "budget": "5억",
        "project_period": "12개월",
        "requirements": [
            {"category": "연구", "description": "R&D 선행연구 분석"},
            {"category": "연구", "description": "실험 데이터 수집 및 논문 발표"},
        ],
    }


def test_plan_wbs_construction_auto_domain():
    """건설 RFP → 자동 도메인 감지 + 건설 템플릿 fallback."""
    with patch("wbs_planner.call_with_retry", side_effect=Exception("LLM down")):
        tasks, personnel, months, methodology = plan_wbs(
            _rfx_construction(),
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
        )
    assert months == 24
    phases = {t.phase for t in tasks}
    assert "시공" in phases
    # Default role should be construction-appropriate
    roles = {t.responsible_role for t in tasks}
    assert "시공관리자" in roles
    assert "개발자" not in roles


def test_plan_wbs_research_auto_domain():
    """연구 RFP → 자동 도메인 감지 + 연구 템플릿 fallback."""
    with patch("wbs_planner.call_with_retry", side_effect=Exception("LLM down")):
        tasks, personnel, months, methodology = plan_wbs(
            _rfx_research(),
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
        )
    assert months == 12
    phases = {t.phase for t in tasks}
    assert "연구수행" in phases
    roles = {t.responsible_role for t in tasks}
    assert "연구원" in roles


def test_plan_wbs_explicit_domain_override():
    """명시적 domain 파라미터가 자동 감지보다 우선."""
    with patch("wbs_planner.call_with_retry", side_effect=Exception("LLM down")):
        tasks, _, _, _ = plan_wbs(
            _rfx_result(),  # IT 키워드 포함
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
            domain="construction",  # 강제 지정
        )
    phases = {t.phase for t in tasks}
    assert "시공" in phases


def test_plan_wbs_it_backward_compat():
    """기존 IT RFP → 기존 동작 유지 (도메인 자동 감지 it_build)."""
    mock_items = {
        "tasks": [
            {
                "phase": "착수",
                "task_name": "사업 착수 보고",
                "start_month": 1,
                "duration_months": 1,
                "deliverables": ["착수보고서"],
                "responsible_role": "PM",
                "man_months": 1.0,
            },
        ]
    }
    mock_response = _mock_llm_resp(json.dumps(mock_items, ensure_ascii=False))

    with patch("wbs_planner.call_with_retry", return_value=mock_response):
        tasks, personnel, months, methodology = plan_wbs(
            _rfx_result(),
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
        )
    assert len(tasks) == 1
    assert tasks[0].responsible_role == "PM"


def test_plan_wbs_personnel_grade_construction():
    """건설 역할의 등급이 올바르게 매핑."""
    mock_items = {
        "tasks": [
            {
                "phase": "착수",
                "task_name": "착수보고",
                "start_month": 1,
                "duration_months": 1,
                "deliverables": ["착수보고서"],
                "responsible_role": "현장소장",
                "man_months": 1.0,
            },
            {
                "phase": "시공",
                "task_name": "토공사",
                "start_month": 2,
                "duration_months": 6,
                "deliverables": ["시공보고서"],
                "responsible_role": "시공관리자",
                "man_months": 5.0,
            },
        ]
    }
    mock_response = _mock_llm_resp(json.dumps(mock_items, ensure_ascii=False))

    with patch("wbs_planner.call_with_retry", return_value=mock_response):
        tasks, personnel, months, methodology = plan_wbs(
            _rfx_construction(),
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
            domain="construction",
        )
    grade_map = {p.role: p.grade for p in personnel}
    assert grade_map["현장소장"] == "특급"
    assert grade_map["시공관리자"] == "고급"


# ---------------------------------------------------------------------------
# Domain template completeness
# ---------------------------------------------------------------------------

def test_all_domain_templates_have_valid_ratios():
    """모든 도메인 템플릿의 ratio 합이 1.0."""
    for domain, methods in DOMAIN_TEMPLATES.items():
        for method, phases in methods.items():
            total = sum(p["ratio"] for p in phases)
            assert abs(total - 1.0) < 0.01, (
                f"DOMAIN_TEMPLATES['{domain}']['{method}'] ratio sum = {total}"
            )


def test_all_domain_templates_have_tasks():
    """모든 도메인 템플릿의 각 phase에 최소 1개 task."""
    for domain, methods in DOMAIN_TEMPLATES.items():
        for method, phases in methods.items():
            for phase in phases:
                assert len(phase["tasks"]) >= 1, (
                    f"DOMAIN_TEMPLATES['{domain}']['{method}'] phase '{phase['phase']}' has no tasks"
                )
