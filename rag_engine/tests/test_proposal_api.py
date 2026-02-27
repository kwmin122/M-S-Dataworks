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
    assert "docx_path" in data
    assert "sections" in data
    assert data["generation_time_sec"] > 0
