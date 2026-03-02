"""Tests for track_record_orchestrator.py."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from track_record_orchestrator import generate_track_record_doc


def _rfx_result():
    return {
        "title": "스마트시티 통합플랫폼 구축",
        "issuing_org": "서울시",
        "budget": "50억",
        "project_period": "12개월",
        "requirements": [
            {"category": "기술", "description": "IoT 센서 통합"},
        ],
    }


def _mock_company_db():
    db = MagicMock()
    db.search_similar_projects.return_value = [
        {
            "text": "관제시스템 구축",
            "metadata": {"project_name": "관제시스템", "client": "부산시", "amount": 30.0},
            "distance": 0.3,
        },
    ]
    db.find_matching_personnel.return_value = [
        {
            "text": "PM 홍길동",
            "metadata": {"name": "홍길동", "role": "PM", "experience_years": 15},
            "distance": 0.2,
        },
    ]
    return db


@patch("track_record_orchestrator.KnowledgeDB")
@patch("track_record_orchestrator.generate_personnel_text", return_value="경력 서술")
@patch("track_record_orchestrator.generate_track_record_text", return_value="실적 서술")
@patch("track_record_orchestrator.CompanyDB")
def test_generate_track_record_doc_creates_docx(MockDB, mock_tr_text, mock_ps_text, mock_kb):
    mock_kb.return_value.search.return_value = []
    MockDB.return_value = _mock_company_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_track_record_doc(
            rfx_result=_rfx_result(),
            output_dir=tmpdir,
            company_db_path=tmpdir,
            max_workers=1,
        )
        assert result.docx_path != ""
        assert os.path.isfile(result.docx_path)
        assert result.track_record_count == 1
        assert result.personnel_count == 1
        assert result.generation_time_sec >= 0


@patch("track_record_orchestrator.KnowledgeDB")
@patch("track_record_orchestrator.CompanyDB")
def test_generate_track_record_doc_empty_db(MockDB, mock_kb):
    mock_kb.return_value.search.return_value = []
    db = MagicMock()
    db.search_similar_projects.return_value = []
    db.find_matching_personnel.return_value = []
    MockDB.return_value = db

    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_track_record_doc(
            rfx_result=_rfx_result(),
            output_dir=tmpdir,
            company_db_path=tmpdir,
        )
        assert result.docx_path == ""
        assert result.track_record_count == 0
        assert result.personnel_count == 0
