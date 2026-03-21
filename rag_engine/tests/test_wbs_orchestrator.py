"""Tests for wbs_orchestrator.py."""
import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from phase2_models import MethodologyType
from wbs_orchestrator import generate_wbs


def _rfx_result():
    return {
        "title": "스마트시티 통합플랫폼 구축",
        "issuing_org": "서울시",
        "budget": "50억",
        "project_period": "8개월",
        "requirements": [
            {"category": "기술", "description": "IoT 센서 통합"},
        ],
    }


def _mock_llm_response():
    """Structured Outputs 형식 {tasks: [...]}."""
    items = {
        "tasks": [
            {"phase": "착수", "task_name": "착수 보고", "start_month": 1, "duration_months": 1,
             "deliverables": ["착수보고서"], "responsible_role": "PM", "man_months": 1.0},
            {"phase": "분석", "task_name": "요구 분석", "start_month": 2, "duration_months": 2,
             "deliverables": ["요구사항정의서"], "responsible_role": "PL", "man_months": 2.0},
        ]
    }
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = json.dumps(items, ensure_ascii=False)
    return resp


@patch("wbs_orchestrator.KnowledgeDB")
@patch("wbs_planner.call_with_retry")
def test_generate_wbs_creates_files(mock_llm, MockKB):
    mock_llm.return_value = _mock_llm_response()
    mock_kb = MagicMock()
    mock_kb.search.return_value = []
    MockKB.return_value = mock_kb

    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_wbs(
            rfx_result=_rfx_result(),
            output_dir=tmpdir,
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
            knowledge_db_path=tmpdir,
        )
        assert os.path.isfile(result.xlsx_path)
        assert os.path.isfile(result.docx_path)
        assert result.total_months == 8
        assert len(result.tasks) == 2
        assert result.generation_time_sec >= 0


@patch("wbs_orchestrator.KnowledgeDB")
@patch("wbs_planner.call_with_retry")
def test_generate_wbs_quality_report_populated(mock_llm, MockKB):
    """WbsResult.quality_report should be populated with expected keys after generation."""
    mock_llm.return_value = _mock_llm_response()
    mock_kb = MagicMock()
    mock_kb.search.return_value = []
    MockKB.return_value = mock_kb

    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_wbs(
            rfx_result=_rfx_result(),
            output_dir=tmpdir,
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
            knowledge_db_path=tmpdir,
        )
        assert isinstance(result.quality_report, dict)
        assert result.quality_report, "quality_report should not be empty"
        assert "overall_score" in result.quality_report
        assert "grade" in result.quality_report
        assert "dimensions" in result.quality_report
        assert isinstance(result.quality_report["dimensions"], list)
        assert len(result.quality_report["dimensions"]) > 0


@patch("wbs_orchestrator.KnowledgeDB")
@patch("wbs_planner.call_with_retry", side_effect=Exception("LLM down"))
def test_generate_wbs_fallback_on_llm_failure(mock_llm, MockKB):
    mock_kb = MagicMock()
    mock_kb.search.return_value = []
    MockKB.return_value = mock_kb

    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_wbs(
            rfx_result=_rfx_result(),
            output_dir=tmpdir,
            methodology=MethodologyType.WATERFALL,
            api_key="test-key",
            knowledge_db_path=tmpdir,
        )
        assert os.path.isfile(result.xlsx_path)
        assert os.path.isfile(result.docx_path)
        assert len(result.tasks) > 0  # fallback tasks
