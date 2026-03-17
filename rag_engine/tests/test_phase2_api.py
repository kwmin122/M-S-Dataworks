"""Tests for Phase 2 API endpoints in main.py."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient


def _rfx_body():
    return {
        "title": "스마트시티 통합플랫폼 구축",
        "issuing_org": "서울시",
        "budget": "50억",
        "project_period": "8개월",
        "evaluation_criteria": [
            {"category": "기술", "max_score": 60.0, "description": "기술 평가"},
        ],
        "requirements": [
            {"category": "기술", "description": "IoT 센서 통합"},
        ],
        "rfp_text_summary": "",
    }


@pytest.fixture
def client():
    """Create test client with mocked proposals dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("main._PROPOSALS_DIR", tmpdir):
            from main import app
            yield TestClient(app)


# ---------------------------------------------------------------------------
# WBS endpoint
# ---------------------------------------------------------------------------

def _mock_wbs_result(tmpdir="/tmp"):
    from phase2_models import WbsResult, WbsTask, PersonnelAllocation
    return WbsResult(
        xlsx_path=os.path.join(tmpdir, "test.xlsx"),
        gantt_path=os.path.join(tmpdir, "test.png"),
        docx_path=os.path.join(tmpdir, "test.docx"),
        tasks=[WbsTask(phase="착수", task_name="착수보고", start_month=1, duration_months=1)],
        personnel=[PersonnelAllocation(role="PM", total_man_months=2.0)],
        total_months=8,
        generation_time_sec=5.0,
    )


@patch("main.asyncio.to_thread")
def test_generate_wbs_endpoint(mock_thread, client):
    mock_thread.return_value = _mock_wbs_result()
    resp = client.post(
        "/api/generate-wbs",
        json={"rfx_result": _rfx_body(), "methodology": "waterfall"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "xlsx_filename" in data
    assert data["tasks_count"] == 1
    assert data["total_months"] == 8


@patch("main.asyncio.to_thread")
def test_generate_wbs_session_context_legacy_path(mock_thread, client):
    """use_pack=false: company_session_context가 wbs_orchestrator로 전달되는지 검증."""
    mock_thread.return_value = _mock_wbs_result()
    session_ctx = "우리 회사는 클라우드 전환 실적 5건, PM 경력 15년"

    resp = client.post(
        "/api/generate-wbs",
        json={
            "rfx_result": _rfx_body(),
            "use_pack": False,
            "company_session_context": session_ctx,
        },
    )
    assert resp.status_code == 200

    # Verify company_session_context was passed to orchestrator
    call_kwargs = mock_thread.call_args
    # asyncio.to_thread(fn, **kwargs) — kwargs are positional after fn
    # Check that company_session_context appears in the call
    call_str = str(call_kwargs)
    assert "클라우드 전환 실적" in call_str, \
        f"company_session_context not passed to orchestrator: {call_str[:200]}"


@patch("main.asyncio.to_thread")
def test_generate_wbs_session_context_pack_path(mock_thread, client):
    """use_pack=true: company_session_context가 company_context에 병합되는지 검증."""
    from phase2_models import WbsResult, WbsTask, PersonnelAllocation
    # Pack path returns a different result type with domain_type
    mock_result = MagicMock()
    mock_result.tasks = [WbsTask(phase="착수", task_name="착수보고", start_month=1, duration_months=1)]
    mock_result.personnel = [PersonnelAllocation(role="PM", total_man_months=2.0)]
    mock_result.total_months = 8
    mock_result.generation_time_sec = 5.0
    mock_result.domain_type = "it_build"
    mock_result.quality_issues = []
    mock_thread.return_value = mock_result

    session_ctx = "보안 컨설팅 실적 3건, ISMS 인증 보유"

    resp = client.post(
        "/api/generate-wbs",
        json={
            "rfx_result": _rfx_body(),
            "use_pack": True,
            "company_session_context": session_ctx,
        },
    )
    assert resp.status_code == 200

    # Verify company_context arg to generate_document includes session context
    call_kwargs = mock_thread.call_args
    call_str = str(call_kwargs)
    assert "보안 컨설팅 실적" in call_str, \
        f"Session context not merged into company_context for pack path: {call_str[:200]}"


@patch("main.asyncio.to_thread")
def test_generate_wbs_empty_session_context(mock_thread, client):
    """company_session_context 빈 문자열이면 기존 동작 그대로."""
    mock_thread.return_value = _mock_wbs_result()
    resp = client.post(
        "/api/generate-wbs",
        json={
            "rfx_result": _rfx_body(),
            "company_session_context": "",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["tasks_count"] == 1


def test_generate_wbs_invalid_methodology(client):
    resp = client.post(
        "/api/generate-wbs",
        json={"rfx_result": _rfx_body(), "methodology": "invalid"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PPT endpoint
# ---------------------------------------------------------------------------

@patch("main.asyncio.to_thread")
def test_generate_ppt_endpoint(mock_thread, client):
    from phase2_models import PptResult, QnaPair
    mock_thread.return_value = PptResult(
        pptx_path="/tmp/test.pptx",
        slide_count=15,
        qna_pairs=[QnaPair(question="Q?", answer="A.", category="기술")],
        total_duration_min=30.0,
        generation_time_sec=10.0,
    )
    resp = client.post(
        "/api/generate-ppt",
        json={
            "rfx_result": _rfx_body(),
            "duration_min": 20,
            "qna_count": 5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["slide_count"] == 15
    assert len(data["qna_pairs"]) == 1


# ---------------------------------------------------------------------------
# Track record endpoint
# ---------------------------------------------------------------------------

@patch("main.asyncio.to_thread")
def test_generate_track_record_endpoint(mock_thread, client):
    from phase2_models import TrackRecordDocResult
    mock_thread.return_value = TrackRecordDocResult(
        docx_path="/tmp/test.docx",
        track_record_count=5,
        personnel_count=3,
        generation_time_sec=8.0,
    )
    resp = client.post(
        "/api/generate-track-record",
        json={"rfx_result": _rfx_body()},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["track_record_count"] == 5
    assert data["personnel_count"] == 3


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_generate_wbs_empty_title_fails(client):
    body = _rfx_body()
    body["title"] = ""
    resp = client.post(
        "/api/generate-wbs",
        json={"rfx_result": body},
    )
    assert resp.status_code == 422


def test_generate_ppt_duration_out_of_range(client):
    resp = client.post(
        "/api/generate-ppt",
        json={"rfx_result": _rfx_body(), "duration_min": 5},  # below 10
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Company DB analyze-style endpoint
# ---------------------------------------------------------------------------

def test_analyze_style_endpoint(client):
    """Test /api/company-db/analyze-style saves writing style to profile."""
    mock_db = MagicMock()
    mock_db.load_profile.return_value = None

    # Patch the cache dict directly — patching the class constructor doesn't work
    # because _get_company_db() caches the instance from earlier tests.
    import main as _main
    original_cache = _main._company_db_cache.copy()
    _main._company_db_cache["_default"] = mock_db
    try:
        docs = [
            "본 사업은 클라우드 전환을 위한 프로젝트이다. 시스템 구조를 개선함.",
            "보안 체계를 강화함. 모니터링 시스템을 구축함.",
        ]
        resp = client.post(
            "/api/company-db/analyze-style",
            json={"documents": docs},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        ws = data["writing_style"]
        assert "tone" in ws
        assert "avg_sentence_length" in ws
        assert "strength_keywords" in ws
        assert ws["tone"] in ("격식체", "경어체", "혼합")
        # Profile should be saved
        mock_db.save_profile.assert_called_once()
    finally:
        _main._company_db_cache.clear()
        _main._company_db_cache.update(original_cache)


def test_analyze_style_empty_documents(client):
    """Test /api/company-db/analyze-style rejects empty documents."""
    resp = client.post(
        "/api/company-db/analyze-style",
        json={"documents": []},
    )
    assert resp.status_code == 422
