"""Tests for ppt_slide_planner.py."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from phase2_models import SlideType
from ppt_slide_planner import plan_slides, generate_qna_pairs


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


def test_plan_slides_default():
    """LLM 실패 시 템플릿 fallback으로 기본 구조 생성."""
    with patch("ppt_slide_planner.call_with_retry", side_effect=Exception("mock LLM failure")):
        slides = plan_slides(_rfx_result())
    assert len(slides) >= 12  # At least 12 from structure
    # Must have cover and closing
    types = [s.slide_type for s in slides]
    assert SlideType.COVER in types
    assert SlideType.CLOSING in types
    assert SlideType.QNA in types


def test_plan_slides_with_duration():
    """발표 시간 분배 검증 (fallback 경로)."""
    with patch("ppt_slide_planner.call_with_retry", side_effect=Exception("mock LLM failure")):
        slides = plan_slides(_rfx_result(), duration_min=20)
    total_sec = sum(s.duration_sec for s in slides)
    # Should distribute close to 20 min
    assert total_sec > 0


def test_plan_slides_with_proposal_sections():
    """제안서 섹션이 있는 경우 (fallback 경로)."""
    sections = [
        {"name": "사업 이해", "text": "본 사업은 스마트시티 구축을 위한..."},
        {"name": "추진 전략", "text": "IoT 센서 기반 전략..."},
    ]
    with patch("ppt_slide_planner.call_with_retry", side_effect=Exception("mock LLM failure")):
        slides = plan_slides(_rfx_result(), proposal_sections=sections)
    assert len(slides) >= 12


def test_plan_slides_llm_generates_content():
    """LLM이 슬라이드 콘텐츠를 생성하는 경우."""
    mock_slides = {
        "slides": [
            {"title": "표지", "body": "", "bullets": [], "speaker_notes": "", "slide_category": "cover"},
            {"title": "사업 이해", "body": "IoT 센서 통합 관제 시스템", "bullets": ["센서 통합", "실시간 모니터링"], "speaker_notes": "핵심 이해도", "slide_category": "content"},
            {"title": "추진 전략", "body": "클라우드 기반 아키텍처", "bullets": ["마이크로서비스", "컨테이너"], "speaker_notes": "전략 설명", "slide_category": "content"},
            {"title": "기술 방안", "body": "IoT 프로토콜 표준화", "bullets": ["MQTT", "REST API"], "speaker_notes": "기술 상세", "slide_category": "content"},
            {"title": "수행 일정", "body": "8개월 WBS", "bullets": ["분석 2개월", "개발 4개월"], "speaker_notes": "일정 설명", "slide_category": "timeline"},
            {"title": "마무리", "body": "", "bullets": [], "speaker_notes": "감사합니다", "slide_category": "closing"},
        ]
    }
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(mock_slides, ensure_ascii=False)
    mock_response.choices[0].finish_reason = "stop"

    with patch("ppt_slide_planner.call_with_retry", return_value=mock_response):
        slides = plan_slides(_rfx_result(), api_key="test-key")
    assert len(slides) == 6
    assert slides[1].body == "IoT 센서 통합 관제 시스템"
    assert len(slides[1].bullets) == 2


def test_generate_qna_pairs_structured_outputs():
    """Structured Outputs 형식 {qna_pairs: [...]} 응답 처리."""
    qna_data = {
        "qna_pairs": [
            {"question": "IoT 보안 대책은?", "answer": "암호화 + 인증...", "category": "기술"},
            {"question": "PM 경력은?", "answer": "15년 경력...", "category": "인력"},
        ]
    }
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(qna_data, ensure_ascii=False)
    mock_response.choices[0].finish_reason = "stop"

    with patch("ppt_slide_planner.call_with_retry", return_value=mock_response):
        pairs = generate_qna_pairs(_rfx_result(), count=5, api_key="test-key")
    assert len(pairs) == 2
    assert pairs[0].question == "IoT 보안 대책은?"
    assert pairs[0].category == "기술"
