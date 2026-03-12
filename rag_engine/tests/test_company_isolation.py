"""E2E isolation tests — verify company_id data boundaries.

Confirms that:
1. Track records/personnel for company_A are invisible to company_B
2. profile.json is stored in separate directories per company_id
3. ChromaDB collections are isolated per company_id
4. Canonical company_id sanitization works consistently
5. Generation endpoints pass the correct cached CompanyDB instance
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def isolated_client():
    """TestClient with temp dirs for proposals + company_db to avoid polluting real data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proposals_dir = os.path.join(tmpdir, "proposals")
        company_db_base = os.path.join(tmpdir, "company_db")
        os.makedirs(proposals_dir, exist_ok=True)
        os.makedirs(company_db_base, exist_ok=True)

        import main as _main
        original_cache = _main._company_db_cache.copy()
        original_base = _main._COMPANY_DB_BASE
        _main._company_db_cache.clear()
        _main._COMPANY_DB_BASE = company_db_base

        with patch("main._PROPOSALS_DIR", proposals_dir):
            from main import app
            client = TestClient(app)
            try:
                yield client, tmpdir, company_db_base
            finally:
                _main._company_db_cache.clear()
                _main._company_db_cache.update(original_cache)
                _main._COMPANY_DB_BASE = original_base


def _create_profile(client, company_id, company_name):
    """Helper: create a company profile (needed before add_track_record can update profile.json)."""
    client.put("/api/company-db/profile", json={
        "company_name": company_name,
        "company_id": company_id,
    })


# ---------------------------------------------------------------------------
# 1. Track record isolation — A의 실적이 B에 안 보임
# ---------------------------------------------------------------------------

def test_track_record_isolation(isolated_client):
    """Company A's track records must NOT appear in company B's list."""
    client, tmpdir, db_base = isolated_client

    # Create profiles first (list_track_records reads from profile.json)
    _create_profile(client, "company_a", "A회사")
    _create_profile(client, "company_b", "B회사")

    # Add track record to company_a
    resp = client.post("/api/company-db/track-records", json={
        "project_name": "서울시 스마트시티",
        "client": "서울시",
        "period": "2024.01~2024.12",
        "description": "IoT 플랫폼 구축",
        "company_id": "company_a",
    })
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Add track record to company_b
    resp = client.post("/api/company-db/track-records", json={
        "project_name": "부산시 교통시스템",
        "client": "부산시",
        "period": "2025.01~2025.06",
        "description": "교통 AI 시스템",
        "company_id": "company_b",
    })
    assert resp.status_code == 200

    # Verify company_a sees only its own
    resp = client.get("/api/company-db/track-records", params={"company_id": "company_a"})
    assert resp.status_code == 200
    records_a = resp.json()["records"]
    assert len(records_a) == 1
    assert records_a[0]["project_name"] == "서울시 스마트시티"

    # Verify company_b sees only its own
    resp = client.get("/api/company-db/track-records", params={"company_id": "company_b"})
    assert resp.status_code == 200
    records_b = resp.json()["records"]
    assert len(records_b) == 1
    assert records_b[0]["project_name"] == "부산시 교통시스템"

    # Verify _default sees nothing (no cross-contamination)
    resp = client.get("/api/company-db/track-records", params={"company_id": "_default"})
    assert resp.status_code == 200
    assert len(resp.json()["records"]) == 0


# ---------------------------------------------------------------------------
# 2. Personnel isolation — A의 인력이 B에 안 보임
# ---------------------------------------------------------------------------

def test_personnel_isolation(isolated_client):
    """Company A's personnel must NOT appear in company B's list."""
    client, tmpdir, db_base = isolated_client

    # Create profiles first
    _create_profile(client, "company_a", "A회사")
    _create_profile(client, "company_b", "B회사")

    # Add personnel to company_a
    resp = client.post("/api/company-db/personnel", json={
        "name": "김철수",
        "role": "PM",
        "experience_years": 15,
        "certifications": ["PMP"],
        "company_id": "company_a",
    })
    assert resp.status_code == 200

    # Add personnel to company_b
    resp = client.post("/api/company-db/personnel", json={
        "name": "이영희",
        "role": "PL",
        "experience_years": 10,
        "certifications": ["정보관리기술사"],
        "company_id": "company_b",
    })
    assert resp.status_code == 200

    # Verify isolation
    resp_a = client.get("/api/company-db/personnel", params={"company_id": "company_a"})
    assert resp_a.status_code == 200
    personnel_a = resp_a.json()["personnel"]
    assert len(personnel_a) == 1
    assert personnel_a[0]["name"] == "김철수"

    resp_b = client.get("/api/company-db/personnel", params={"company_id": "company_b"})
    assert resp_b.status_code == 200
    personnel_b = resp_b.json()["personnel"]
    assert len(personnel_b) == 1
    assert personnel_b[0]["name"] == "이영희"


# ---------------------------------------------------------------------------
# 3. Profile isolation — 별도 디렉토리에 profile.json 저장
# ---------------------------------------------------------------------------

def test_profile_directory_isolation(isolated_client):
    """Each company_id gets its own directory under _COMPANY_DB_BASE."""
    client, tmpdir, db_base = isolated_client

    # Create profiles for two companies
    client.put("/api/company-db/profile", json={
        "company_name": "A회사",
        "employee_count": 100,
        "company_id": "company_a",
    })
    client.put("/api/company-db/profile", json={
        "company_name": "B회사",
        "employee_count": 50,
        "company_id": "company_b",
    })

    # Verify separate directories exist
    dir_a = os.path.join(db_base, "company_a")
    dir_b = os.path.join(db_base, "company_b")
    assert os.path.isdir(dir_a), f"company_a dir missing: {dir_a}"
    assert os.path.isdir(dir_b), f"company_b dir missing: {dir_b}"

    # Verify separate profile.json files
    profile_a_path = os.path.join(dir_a, "profile.json")
    profile_b_path = os.path.join(dir_b, "profile.json")
    assert os.path.isfile(profile_a_path), "company_a profile.json missing"
    assert os.path.isfile(profile_b_path), "company_b profile.json missing"

    with open(profile_a_path, encoding="utf-8") as f:
        pa = json.load(f)
    with open(profile_b_path, encoding="utf-8") as f:
        pb = json.load(f)

    assert pa["name"] == "A회사"
    assert pb["name"] == "B회사"
    assert pa["employee_count"] == 100
    assert pb["employee_count"] == 50


# ---------------------------------------------------------------------------
# 4. Profile API isolation — GET returns correct company data
# ---------------------------------------------------------------------------

def test_profile_api_isolation(isolated_client):
    """GET /api/company-db/profile returns data for the requested company_id only."""
    client, tmpdir, db_base = isolated_client

    # Setup two companies
    client.put("/api/company-db/profile", json={
        "company_name": "Alpha Corp",
        "company_id": "alpha",
    })
    client.put("/api/company-db/profile", json={
        "company_name": "Beta Inc",
        "company_id": "beta",
    })

    # Verify
    resp_a = client.get("/api/company-db/profile", params={"company_id": "alpha"})
    assert resp_a.json()["profile"]["company_name"] == "Alpha Corp"
    assert resp_a.json()["profile"]["company_id"] == "alpha"

    resp_b = client.get("/api/company-db/profile", params={"company_id": "beta"})
    assert resp_b.json()["profile"]["company_name"] == "Beta Inc"
    assert resp_b.json()["profile"]["company_id"] == "beta"

    # Unknown company returns null profile
    resp_x = client.get("/api/company-db/profile", params={"company_id": "nonexistent"})
    assert resp_x.json()["profile"] is None


# ---------------------------------------------------------------------------
# 5. Stats isolation
# ---------------------------------------------------------------------------

def test_stats_isolation(isolated_client):
    """Stats endpoint returns per-company counts."""
    client, tmpdir, db_base = isolated_client

    _create_profile(client, "company_a", "A회사")
    _create_profile(client, "company_b", "B회사")

    # Add 2 records to company_a, 1 to company_b
    for name in ["프로젝트1", "프로젝트2"]:
        client.post("/api/company-db/track-records", json={
            "project_name": name,
            "client": "발주처",
            "company_id": "company_a",
        })
    client.post("/api/company-db/track-records", json={
        "project_name": "프로젝트X",
        "client": "다른발주처",
        "company_id": "company_b",
    })

    stats_a = client.get("/api/company-db/stats", params={"company_id": "company_a"}).json()
    stats_b = client.get("/api/company-db/stats", params={"company_id": "company_b"}).json()

    assert stats_a["track_record_count"] == 2
    assert stats_b["track_record_count"] == 1
    assert stats_a["total_knowledge_units"] == 2
    assert stats_b["total_knowledge_units"] == 1


# ---------------------------------------------------------------------------
# 6. Delete isolation — deleting from A doesn't affect B
# ---------------------------------------------------------------------------

def test_delete_isolation(isolated_client):
    """Deleting a doc from company_a must not affect company_b."""
    client, tmpdir, db_base = isolated_client

    _create_profile(client, "company_a", "A회사")
    _create_profile(client, "company_b", "B회사")

    # Add same-name project to both companies
    resp_a = client.post("/api/company-db/track-records", json={
        "project_name": "공통프로젝트",
        "client": "발주처A",
        "company_id": "company_a",
    })
    resp_b = client.post("/api/company-db/track-records", json={
        "project_name": "공통프로젝트",
        "client": "발주처B",
        "company_id": "company_b",
    })

    doc_id_a = resp_a.json()["id"]
    doc_id_b = resp_b.json()["id"]

    # Delete from company_a
    del_resp = client.delete(f"/api/company-db/items/{doc_id_a}", params={"company_id": "company_a"})
    assert del_resp.status_code == 200

    # company_a should have 0 records
    assert len(client.get("/api/company-db/track-records", params={"company_id": "company_a"}).json()["records"]) == 0

    # company_b should still have 1 record
    records_b = client.get("/api/company-db/track-records", params={"company_id": "company_b"}).json()["records"]
    assert len(records_b) == 1
    assert records_b[0]["project_name"] == "공통프로젝트"


# ---------------------------------------------------------------------------
# 7. Canonical company_id — sanitization consistency
# ---------------------------------------------------------------------------

def test_canonical_company_id_sanitization(isolated_client):
    """Canonical ID endpoint produces safe, consistent IDs."""
    client, tmpdir, db_base = isolated_client

    # Korean name with special chars
    resp = client.get("/api/company-db/canonical-id", params={"company_name": "(주) M&S Solutions"})
    assert resp.status_code == 200
    cid = resp.json()["company_id"]
    assert cid == "주_M_S_Solutions"

    # Same input → same output (idempotent)
    resp2 = client.get("/api/company-db/canonical-id", params={"company_name": "(주) M&S Solutions"})
    assert resp2.json()["company_id"] == cid

    # Empty → _default
    resp3 = client.get("/api/company-db/canonical-id", params={"company_name": ""})
    assert resp3.json()["company_id"] == "_default"

    # Already safe name passes through
    resp4 = client.get("/api/company-db/canonical-id", params={"company_name": "simple_company"})
    assert resp4.json()["company_id"] == "simple_company"

    # URL-encoded special chars (simulates web_app's urllib.parse.quote call)
    import urllib.parse
    encoded_name = urllib.parse.quote("(주) M&S Solutions", safe="")
    resp5 = client.get(f"/api/company-db/canonical-id?company_name={encoded_name}")
    assert resp5.status_code == 200
    assert resp5.json()["company_id"] == cid  # must match the params= version


# ---------------------------------------------------------------------------
# 8. Invalid company_id rejected
# ---------------------------------------------------------------------------

def test_invalid_company_id_rejected(isolated_client):
    """Path traversal and special characters in company_id must be rejected."""
    client, tmpdir, db_base = isolated_client

    # Path traversal attempt
    resp = client.get("/api/company-db/track-records", params={"company_id": "../etc/passwd"})
    assert resp.status_code == 400

    resp = client.get("/api/company-db/profile", params={"company_id": "../../secrets"})
    assert resp.status_code == 400

    # Special characters
    resp = client.get("/api/company-db/stats", params={"company_id": "a;rm -rf /"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 9. Generation endpoints pass cached CompanyDB instance
# ---------------------------------------------------------------------------

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


@patch("main.asyncio.to_thread")
def test_wbs_generation_passes_company_db_instance(mock_thread, isolated_client):
    """WBS generation must pass per-company CompanyDB instance + path to orchestrator."""
    client, tmpdir, db_base = isolated_client

    from phase2_models import WbsResult, WbsTask, PersonnelAllocation
    mock_thread.return_value = WbsResult(
        xlsx_path=os.path.join(tmpdir, "test.xlsx"),
        gantt_path=os.path.join(tmpdir, "test.png"),
        docx_path=os.path.join(tmpdir, "test.docx"),
        tasks=[WbsTask(phase="착수", task_name="착수보고", start_month=1, duration_months=1)],
        personnel=[PersonnelAllocation(role="PM", total_man_months=2.0)],
        total_months=8,
        generation_time_sec=5.0,
    )

    resp = client.post("/api/generate-wbs", json={
        "rfx_result": _rfx_body(),
        "methodology": "waterfall",
        "company_id": "test_wbs_co",
    })
    assert resp.status_code == 200

    # Verify kwargs passed to asyncio.to_thread → orchestrator
    call_args = mock_thread.call_args
    assert call_args is not None
    _, kwargs = call_args
    # company_db_path must point to per-company directory
    assert "test_wbs_co" in kwargs["company_db_path"]
    # company_db must be a live CompanyDB instance (not None)
    assert kwargs["company_db"] is not None
    assert hasattr(kwargs["company_db"], "load_profile")
    assert hasattr(kwargs["company_db"], "search_similar_projects")


@patch("main.asyncio.to_thread")
def test_ppt_generation_passes_company_db_instance(mock_thread, isolated_client):
    """PPT generation must pass per-company CompanyDB instance + path to orchestrator."""
    client, tmpdir, db_base = isolated_client

    from phase2_models import PptResult, QnaPair
    mock_thread.return_value = PptResult(
        pptx_path=os.path.join(tmpdir, "test.pptx"),
        slide_count=15,
        qna_pairs=[QnaPair(question="Q?", answer="A.", category="기술")],
        total_duration_min=30.0,
        generation_time_sec=10.0,
    )

    resp = client.post("/api/generate-ppt", json={
        "rfx_result": _rfx_body(),
        "duration_min": 20,
        "qna_count": 5,
        "company_id": "test_ppt_co",
    })
    assert resp.status_code == 200

    call_args = mock_thread.call_args
    assert call_args is not None
    _, kwargs = call_args
    assert "test_ppt_co" in kwargs["company_db_path"]
    assert kwargs["company_db"] is not None
    assert hasattr(kwargs["company_db"], "load_profile")


@patch("main.asyncio.to_thread")
def test_track_record_generation_passes_company_db_instance(mock_thread, isolated_client):
    """Track record generation must pass per-company CompanyDB instance + path."""
    client, tmpdir, db_base = isolated_client

    from phase2_models import TrackRecordDocResult
    mock_thread.return_value = TrackRecordDocResult(
        docx_path=os.path.join(tmpdir, "test.docx"),
        track_record_count=5,
        personnel_count=3,
        generation_time_sec=8.0,
    )

    resp = client.post("/api/generate-track-record", json={
        "rfx_result": _rfx_body(),
        "company_id": "test_tr_co",
    })
    assert resp.status_code == 200

    call_args = mock_thread.call_args
    assert call_args is not None
    _, kwargs = call_args
    assert "test_tr_co" in kwargs["company_db_path"]
    assert kwargs["company_db"] is not None
    assert hasattr(kwargs["company_db"], "load_profile")


@patch("main.asyncio.to_thread")
def test_proposal_v2_generation_passes_company_db_instance(mock_thread, isolated_client):
    """Proposal v2 generation must pass per-company CompanyDB instance + path."""
    client, tmpdir, db_base = isolated_client

    from proposal_orchestrator import ProposalResult
    mock_thread.return_value = ProposalResult(
        docx_path=os.path.join(tmpdir, "test.docx"),
        sections=[("테스트", "내용")],
        generation_time_sec=10.0,
    )

    resp = client.post("/api/generate-proposal-v2", json={
        "rfx_result": _rfx_body(),
        "company_id": "test_prop_co",
    })
    assert resp.status_code == 200

    call_args = mock_thread.call_args
    assert call_args is not None
    _, kwargs = call_args
    assert "test_prop_co" in kwargs["company_db_path"]
    assert kwargs["company_db"] is not None
    assert hasattr(kwargs["company_db"], "load_profile")


# ---------------------------------------------------------------------------
# 10. Two companies don't share DB instances
# ---------------------------------------------------------------------------

def test_different_companies_get_different_db_instances(isolated_client):
    """Two different company_ids must produce separate CompanyDB instances in cache."""
    client, tmpdir, db_base = isolated_client
    import main as _main

    # Trigger creation of two company DBs
    _create_profile(client, "alpha_co", "Alpha")
    _create_profile(client, "beta_co", "Beta")

    # Both should be in cache
    assert "alpha_co" in _main._company_db_cache
    assert "beta_co" in _main._company_db_cache

    # They must be different objects
    db_alpha = _main._company_db_cache["alpha_co"]
    db_beta = _main._company_db_cache["beta_co"]
    assert db_alpha is not db_beta

    # Their profile paths must point to different directories
    assert "alpha_co" in db_alpha._profile_path
    assert "beta_co" in db_beta._profile_path


# ---------------------------------------------------------------------------
# 11. Full lifecycle isolation: create, list, delete across two companies
# ---------------------------------------------------------------------------

def test_full_lifecycle_two_companies(isolated_client):
    """Full CRUD lifecycle with two companies — no cross-contamination at any step."""
    client, tmpdir, db_base = isolated_client

    # --- Setup company profiles ---
    client.put("/api/company-db/profile", json={
        "company_name": "A테크",
        "employee_count": 200,
        "company_id": "a_tech",
    })
    client.put("/api/company-db/profile", json={
        "company_name": "B시스템즈",
        "employee_count": 80,
        "company_id": "b_systems",
    })

    # --- Add data to both ---
    # A: 2 track records + 1 personnel
    tr1 = client.post("/api/company-db/track-records", json={
        "project_name": "A-프로젝트1", "client": "고객1", "company_id": "a_tech",
    }).json()
    client.post("/api/company-db/track-records", json={
        "project_name": "A-프로젝트2", "client": "고객2", "company_id": "a_tech",
    })
    client.post("/api/company-db/personnel", json={
        "name": "A-김PM", "role": "PM", "experience_years": 20, "company_id": "a_tech",
    })

    # B: 1 track record + 2 personnel
    client.post("/api/company-db/track-records", json={
        "project_name": "B-프로젝트1", "client": "B고객", "company_id": "b_systems",
    })
    client.post("/api/company-db/personnel", json={
        "name": "B-이PL", "role": "PL", "experience_years": 10, "company_id": "b_systems",
    })
    client.post("/api/company-db/personnel", json={
        "name": "B-박개발", "role": "개발자", "experience_years": 5, "company_id": "b_systems",
    })

    # --- Verify counts ---
    stats_a = client.get("/api/company-db/stats", params={"company_id": "a_tech"}).json()
    stats_b = client.get("/api/company-db/stats", params={"company_id": "b_systems"}).json()

    assert stats_a["track_record_count"] == 2
    assert stats_a["personnel_count"] == 1
    assert stats_b["track_record_count"] == 1
    assert stats_b["personnel_count"] == 2

    # --- Delete one record from A ---
    doc_id = tr1["id"]
    client.delete(f"/api/company-db/items/{doc_id}", params={"company_id": "a_tech"})

    # A should have 1 track record now
    stats_a2 = client.get("/api/company-db/stats", params={"company_id": "a_tech"}).json()
    assert stats_a2["track_record_count"] == 1

    # B should be completely unaffected
    stats_b2 = client.get("/api/company-db/stats", params={"company_id": "b_systems"}).json()
    assert stats_b2["track_record_count"] == 1
    assert stats_b2["personnel_count"] == 2

    # --- Verify profiles are still correct ---
    profile_a = client.get("/api/company-db/profile", params={"company_id": "a_tech"}).json()
    profile_b = client.get("/api/company-db/profile", params={"company_id": "b_systems"}).json()
    assert profile_a["profile"]["company_name"] == "A테크"
    assert profile_b["profile"]["company_name"] == "B시스템즈"

    # --- Verify _default is still empty ---
    stats_default = client.get("/api/company-db/stats", params={"company_id": "_default"}).json()
    assert stats_default["track_record_count"] == 0
    assert stats_default["personnel_count"] == 0
