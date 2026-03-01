from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_generate_profile_creates_md():
    """POST /api/company-profile/generate creates profile.md."""
    with patch("main._get_company_skills_dir") as mock_dir:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mock_dir.return_value = tmp
            resp = client.post("/api/company-profile/generate", json={
                "company_name": "테스트기업",
                "documents": ["본 사업은 클라우드 전환을 위한 프로젝트입니다. 본 사업의 목적은 IT 인프라 현대화입니다."],
            })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "테스트기업" in data["profile_md"]


def test_get_profile_returns_content():
    """GET /api/company-profile returns saved content."""
    with patch("main._get_company_skills_dir") as mock_dir:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mock_dir.return_value = tmp
            # Save a profile first
            from company_profile_builder import save_profile_md
            save_profile_md(tmp, "# 테스트 프로필\n\n내용")
            resp = client.get("/api/company-profile")
    assert resp.status_code == 200
    assert "테스트 프로필" in resp.json()["profile_md"]


def test_get_profile_empty():
    """GET /api/company-profile with no profile returns empty."""
    with patch("main._get_company_skills_dir") as mock_dir:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mock_dir.return_value = os.path.join(tmp, "nonexist")
            resp = client.get("/api/company-profile")
    assert resp.status_code == 200
    assert resp.json()["profile_md"] == ""


def test_update_profile_saves_content():
    """PUT /api/company-profile saves content."""
    with patch("main._get_company_skills_dir") as mock_dir:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mock_dir.return_value = tmp
            resp = client.put("/api/company-profile", json={
                "profile_md": "# 수정된 프로필\n\n내용",
            })
            assert resp.status_code == 200
            assert resp.json()["ok"] is True
            # Verify saved
            from company_profile_builder import load_profile_md
            loaded = load_profile_md(tmp)
            assert "수정된 프로필" in loaded


def test_generate_profile_validates_empty_name():
    """POST /api/company-profile/generate rejects empty company_name."""
    resp = client.post("/api/company-profile/generate", json={
        "company_name": "",
        "documents": ["텍스트"],
    })
    assert resp.status_code == 422
