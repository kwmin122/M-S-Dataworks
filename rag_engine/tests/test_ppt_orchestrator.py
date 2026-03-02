"""Tests for ppt_orchestrator.py."""
import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from ppt_orchestrator import generate_ppt


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


def _mock_llm_resp(content: str, finish_reason: str = "stop") -> MagicMock:
    """LLM mock response 생성 헬퍼. finish_reason 명시적 설정."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.choices[0].finish_reason = finish_reason
    return resp


def _mock_qna_response():
    """Structured Outputs 형식 {qna_pairs: [...]} QnA 응답."""
    data = {
        "qna_pairs": [
            {"question": "IoT 보안?", "answer": "암호화 적용", "category": "기술"},
        ]
    }
    return _mock_llm_resp(json.dumps(data, ensure_ascii=False))


@patch("ppt_orchestrator.KnowledgeDB")
@patch("ppt_slide_planner.call_with_retry")
def test_generate_ppt_creates_file(mock_llm, mock_kb):
    mock_kb.return_value.search.return_value = []
    mock_llm.return_value = _mock_qna_response()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_ppt(
            rfx_result=_rfx_result(),
            output_dir=tmpdir,
            duration_min=20,
            qna_count=3,
            api_key="test-key",
            max_workers=1,
        )
        assert os.path.isfile(result.pptx_path)
        assert result.slide_count > 0
        assert result.generation_time_sec >= 0


@patch("ppt_orchestrator.KnowledgeDB")
@patch("ppt_slide_planner.call_with_retry", side_effect=Exception("LLM down"))
def test_generate_ppt_without_qna(mock_llm, mock_kb):
    mock_kb.return_value.search.return_value = []
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_ppt(
            rfx_result=_rfx_result(),
            output_dir=tmpdir,
            duration_min=20,
            qna_count=0,
            api_key="test-key",
            max_workers=1,
        )
        assert os.path.isfile(result.pptx_path)
        assert result.slide_count > 0
        assert len(result.qna_pairs) == 0  # LLM failed, no QnA
