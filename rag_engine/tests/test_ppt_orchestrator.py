"""Tests for ppt_orchestrator.py."""
import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from ppt_orchestrator import generate_ppt, _match_section_to_slide


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


class TestMatchSectionToSlide:
    """_match_section_to_slide keyword scoring tests."""

    def test_exact_match(self):
        sections = [
            {"name": "사업 이해", "text": "사업 이해 내용"},
            {"name": "추진 전략", "text": "전략 내용"},
        ]
        assert _match_section_to_slide("사업 이해", sections) == "사업 이해 내용"

    def test_substring_match(self):
        sections = [
            {"name": "1. 사업 이해 및 분석", "text": "분석 결과"},
        ]
        # slide title is a substring of section name → bonus score
        assert _match_section_to_slide("사업 이해", sections) == "분석 결과"

    def test_partial_overlap_match(self):
        sections = [
            {"name": "기술 구현 방안", "text": "기술 내용"},
            {"name": "일정 및 인력", "text": "인력 내용"},
        ]
        # "기술 방안" overlaps more with "기술 구현 방안" than "일정 및 인력"
        result = _match_section_to_slide("기술 방안", sections)
        assert result == "기술 내용"

    def test_no_match(self):
        sections = [
            {"name": "ABC", "text": "텍스트"},
        ]
        # Completely disjoint characters
        result = _match_section_to_slide("XYZ", sections)
        assert result == ""

    def test_empty_sections(self):
        assert _match_section_to_slide("슬라이드 제목", []) == ""

    def test_empty_slide_title(self):
        sections = [{"name": "섹션", "text": "내용"}]
        assert _match_section_to_slide("", sections) == ""
