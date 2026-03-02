"""Tests for ppt_content_extractor.py."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from phase2_models import SlideType
from ppt_content_extractor import extract_slide_content, extract_key_messages


def _mock_llm_resp(content: str, finish_reason: str = "stop") -> MagicMock:
    """LLM mock response 생성 헬퍼. finish_reason 명시적 설정."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.choices[0].finish_reason = finish_reason
    return resp


def test_extract_slide_content_calls_llm():
    mock_data = {
        "title": "사업 이해",
        "body": "스마트시티 통합 관제 시스템",
        "bullets": ["IoT 센서 통합", "실시간 모니터링", "빅데이터 분석"],
        "speaker_notes": "이 슬라이드에서는 사업의 핵심 이해도를 보여줍니다.",
    }
    mock_response = _mock_llm_resp(json.dumps(mock_data, ensure_ascii=False))

    with patch("ppt_content_extractor.call_with_retry", return_value=mock_response):
        result = extract_slide_content(
            section_name="사업 이해",
            section_text="스마트시티 통합플랫폼 구축 사업은...",
            slide_type=SlideType.CONTENT,
            api_key="test-key",
        )
    assert result.title == "사업 이해"
    assert len(result.bullets) == 3
    assert result.speaker_notes != ""


def test_extract_slide_content_with_knowledge_and_rfp():
    """Layer 1 지식 + RFP 컨텍스트가 주입되는 경우."""
    mock_data = {
        "title": "기술 방안",
        "body": "IoT 프로토콜 표준화 기반 통합 관제",
        "bullets": ["MQTT 기반 센서 통신", "REST API 게이트웨이", "실시간 대시보드"],
        "speaker_notes": "IoT 프로토콜 표준화를 통해 다양한 센서를 통합합니다.",
    }
    mock_response = _mock_llm_resp(json.dumps(mock_data, ensure_ascii=False))

    with patch("ppt_content_extractor.call_with_retry", return_value=mock_response):
        result = extract_slide_content(
            section_name="기술 방안",
            section_text="IoT 프로토콜 표준화를 통한...",
            slide_type=SlideType.CONTENT,
            api_key="test-key",
            knowledge_texts=["PT 슬라이드 불렛은 3~5개 구체적 내용"],
            rfp_context="사업명: 스마트시티 통합플랫폼 구축\n예산: 50억",
        )
    assert result.title == "기술 방안"
    assert "MQTT" in result.bullets[0]
    assert result.slide_type == SlideType.CONTENT


def test_extract_slide_content_truncated_uses_fallback():
    """finish_reason='length' → fallback."""
    mock_response = _mock_llm_resp('{"title": "잘린', finish_reason="length")

    with patch("ppt_content_extractor.call_with_retry", return_value=mock_response):
        result = extract_slide_content(
            section_name="추진 전략",
            section_text="본 사업의 추진 전략은...",
            slide_type=SlideType.CONTENT,
            api_key="test-key",
        )
    assert result.title == "추진 전략"  # fallback title
    assert result.body != ""  # fallback uses raw text


def test_extract_slide_content_fallback_on_error():
    with patch("ppt_content_extractor.call_with_retry", side_effect=Exception("LLM down")):
        result = extract_slide_content(
            section_name="추진 전략",
            section_text="본 사업의 추진 전략은...",
            slide_type=SlideType.CONTENT,
            api_key="test-key",
        )
    assert result.title == "추진 전략"
    assert result.body != ""  # fallback uses raw text


def test_extract_key_messages():
    messages = ["IoT 통합 역량 보유", "15년 공공 IT 경력", "100% 일정 준수율"]
    mock_response = _mock_llm_resp(json.dumps(messages, ensure_ascii=False))

    with patch("ppt_content_extractor.call_with_retry", return_value=mock_response):
        result = extract_key_messages("제안서 전문...", max_messages=5, api_key="test-key")
    assert len(result) == 3
