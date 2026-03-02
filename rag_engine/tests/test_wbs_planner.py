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
    _fallback_tasks,
    plan_wbs,
    WATERFALL_TEMPLATE,
    AGILE_TEMPLATE,
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
