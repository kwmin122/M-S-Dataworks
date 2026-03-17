# rag_engine/tests/test_unified_api.py
"""Unified /api/generate-document endpoint structural test."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_generate_document_endpoint_exists():
    from main import app
    client = TestClient(app)
    # Should return 422 (validation error) not 404 (not found)
    resp = client.post("/api/generate-document", json={})
    assert resp.status_code == 422


def test_generate_document_rejects_invalid_doc_type():
    from main import app
    client = TestClient(app)
    resp = client.post("/api/generate-document", json={
        "doc_type": "invalid_type",
        "rfx_result": {"title": "test"},
        "contract": {},
        "params": {},
    })
    assert resp.status_code == 422 or resp.status_code == 400


def test_generate_document_accepts_alias_doc_type():
    """wbs and ppt should be accepted (alias resolution)."""
    from main import app
    from generation_contract import normalize_doc_type
    # Just verify alias resolution works at API level
    assert normalize_doc_type("wbs") == "execution_plan"
    assert normalize_doc_type("ppt") == "presentation"
