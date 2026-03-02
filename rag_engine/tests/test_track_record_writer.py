"""Tests for track_record_writer.py."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from phase2_models import TrackRecordEntry, PersonnelEntry
from track_record_writer import (
    select_track_records,
    select_personnel,
    generate_track_record_text,
    generate_personnel_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _rfx_result():
    return {
        "title": "스마트시티 통합플랫폼 구축",
        "issuing_org": "서울시",
        "budget": "50억",
        "project_period": "12개월",
        "requirements": [
            {"category": "기술", "description": "IoT 센서 통합"},
            {"category": "인력", "description": "PM 경력 10년 이상"},
        ],
    }


def _mock_company_db(projects=None, personnel=None):
    db = MagicMock()
    db.search_similar_projects.return_value = projects or [
        {
            "text": "스마트시티 관제시스템 구축",
            "metadata": {"project_name": "관제시스템", "client": "부산시", "amount": 30.0},
            "distance": 0.3,
        },
        {
            "text": "IoT 플랫폼 개발",
            "metadata": {"project_name": "IoT플랫폼", "client": "과기부", "amount": 20.0},
            "distance": 0.5,
        },
    ]
    db.find_matching_personnel.return_value = personnel or [
        {
            "text": "PM 홍길동",
            "metadata": {"name": "홍길동", "role": "PM", "experience_years": 15},
            "distance": 0.2,
        },
    ]
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_select_track_records_returns_sorted_by_relevance():
    db = _mock_company_db()
    result = select_track_records(_rfx_result(), db, max_records=5)
    assert len(result) == 2
    assert result[0].relevance_score >= result[1].relevance_score
    assert result[0].project_name == "관제시스템"


def test_select_track_records_respects_max():
    db = _mock_company_db()
    result = select_track_records(_rfx_result(), db, max_records=1)
    assert len(result) == 1


def test_select_personnel_returns_entries():
    db = _mock_company_db()
    result = select_personnel(_rfx_result(), db, max_personnel=5)
    assert len(result) == 1
    assert result[0].name == "홍길동"
    assert result[0].role == "PM"


def _mock_llm_resp(content: str) -> MagicMock:
    """LLM mock response 생성 헬퍼."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


def test_generate_track_record_text_calls_llm():
    entry = TrackRecordEntry(
        project_name="테스트 프로젝트",
        client="테스트 발주처",
        period="2024.01~2024.12",
        amount=10.0,
        description="테스트 설명",
    )
    mock_response = _mock_llm_resp("생성된 실적 서술 텍스트")

    with patch("track_record_writer.call_with_retry", return_value=mock_response):
        text = generate_track_record_text(entry, "RFP 컨텍스트", api_key="test-key")
    assert "생성된 실적 서술 텍스트" in text


def test_generate_track_record_text_with_knowledge():
    """Layer 1 지식이 주입되는 경우."""
    entry = TrackRecordEntry(
        project_name="IoT 관제시스템 구축",
        client="부산시",
        period="2024.01~2024.12",
        amount=30.0,
        description="IoT 센서 기반 스마트시티 관제시스템 구축",
        technologies=["IoT", "클라우드", "빅데이터"],
    )
    mock_response = _mock_llm_resp("IoT 센서 기반 통합 관제시스템 구축 사업을 성공적으로 수행")

    knowledge = [
        "유사실적 서술 시 RFP 과업과의 기술적 연관성을 명시해야 함",
        "수치 기반 성과(사용자 수, 처리량 등)를 포함해야 높은 점수",
    ]

    with patch("track_record_writer.call_with_retry", return_value=mock_response):
        text = generate_track_record_text(
            entry, "사업명: 스마트시티 통합플랫폼 구축",
            api_key="test-key",
            knowledge_texts=knowledge,
        )
    assert "IoT 센서" in text


def test_generate_personnel_text_calls_llm():
    entry = PersonnelEntry(
        name="김철수",
        role="PL",
        experience_years=10,
        certifications=["PMP"],
    )
    mock_response = _mock_llm_resp("생성된 경력 서술")

    with patch("track_record_writer.call_with_retry", return_value=mock_response):
        text = generate_personnel_text(entry, "RFP 컨텍스트", api_key="test-key")
    assert "생성된 경력 서술" in text


def test_generate_personnel_text_with_knowledge():
    """Layer 1 지식이 주입되는 경우."""
    entry = PersonnelEntry(
        name="홍길동",
        role="PM",
        experience_years=15,
        certifications=["PMP", "CISA"],
        key_projects=["스마트시티 관제", "교통정보 시스템"],
    )
    mock_response = _mock_llm_resp("15년 경력의 공공 IT PM으로서 스마트시티 관련 다수 프로젝트 수행")

    knowledge = [
        "경력기술서에 RFP 요구 자격증과 보유 자격증의 매칭을 명시",
    ]

    with patch("track_record_writer.call_with_retry", return_value=mock_response):
        text = generate_personnel_text(
            entry, "사업명: 스마트시티 통합플랫폼 구축",
            api_key="test-key",
            knowledge_texts=knowledge,
        )
    assert "15년 경력" in text
