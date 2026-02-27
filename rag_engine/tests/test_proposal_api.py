from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_generate_proposal_v2_endpoint_via_orchestrator(client):
    """Test the v2 endpoint with mocked orchestrator."""
    from proposal_orchestrator import ProposalResult
    from knowledge_models import ProposalOutline

    mock_result = ProposalResult(
        docx_path="/tmp/test.docx",
        sections=[("제안 개요", "내용")],
        outline=ProposalOutline(title="테스트", issuing_org="기관", sections=[]),
        quality_issues=[],
        generation_time_sec=5.0,
    )

    with patch("proposal_orchestrator.generate_proposal", return_value=mock_result):
        resp = client.post("/api/generate-proposal-v2", json={
            "rfx_result": {
                "title": "테스트",
                "issuing_org": "기관",
                "evaluation_criteria": [],
                "requirements": [],
            },
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "docx_filename" in data
    assert data["docx_filename"] == "test.docx"  # basename only, no server path
    assert "sections" in data
    assert data["generation_time_sec"] > 0


def test_generate_proposal_v2_rejects_missing_title(client):
    """FastAPI returns 422 when rfx_result.title is missing or blank."""
    resp = client.post("/api/generate-proposal-v2", json={
        "rfx_result": {
            "title": "",
            "issuing_org": "기관",
        },
    })
    assert resp.status_code == 422


def test_generate_proposal_v2_rejects_invalid_total_pages(client):
    """FastAPI returns 422 when total_pages is out of range (10~200)."""
    resp = client.post("/api/generate-proposal-v2", json={
        "rfx_result": {"title": "테스트", "issuing_org": "기관"},
        "total_pages": 5,
    })
    assert resp.status_code == 422

    resp2 = client.post("/api/generate-proposal-v2", json={
        "rfx_result": {"title": "테스트", "issuing_org": "기관"},
        "total_pages": 300,
    })
    assert resp2.status_code == 422


def test_checklist_rejects_missing_title(client):
    """Checklist endpoint also validates rfx_result."""
    resp = client.post("/api/checklist", json={
        "rfx_result": {"title": "", "issuing_org": "기관"},
    })
    assert resp.status_code == 422


def test_edit_feedback_rejects_blank_company_id(client):
    """Edit feedback rejects blank company_id."""
    resp = client.post("/api/edit-feedback", json={
        "company_id": "",
        "section_name": "test",
        "original_text": "a",
        "edited_text": "b",
    })
    assert resp.status_code == 422
