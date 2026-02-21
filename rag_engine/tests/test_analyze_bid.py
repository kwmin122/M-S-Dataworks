import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SAMPLE_FACTS = {
    "_meta": {"schemaVersion": "1.0", "updatedAt": "2026-01-01T00:00:00Z", "source": "manual_input"},
    "facts": {
        "region": "경기도",
        "foundationDate": "2015-05-01",
        "capital": 100000000,
        "licenses": [{"code": "0037", "name": "정보통신공사업"}],
        "certifications": [],
        "pastPerformances": [],
    },
}

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_analyze_bid_returns_valid_shape():
    r = client.post("/api/analyze-bid", json={
        "organization_id": "org_test",
        "bid_notice_id": "notice_test",
        "company_facts": SAMPLE_FACTS,
        "attachment_text": "정보통신공사업 면허 보유 업체 입찰 가능",
    })
    # 503 is acceptable when OPENAI_API_KEY is not set (graceful degradation)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        body = r.json()
        assert "is_eligible" in body
        assert "details" in body
        assert "_meta" in body["details"]
        assert "evaluation" in body["details"]
        assert "action_plan" in body
