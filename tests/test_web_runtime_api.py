from pathlib import Path
import urllib.parse
import sys

import pytest

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.web_app import main as web_main
from services.web_app.main import app
from matcher import MatchStatus, MatchingResult, RequirementMatch
from rfx_analyzer import RFxRequirement


client = TestClient(app)


def test_web_runtime_session_bootstrap() -> None:
    create_resp = client.post("/api/session")
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]
    assert isinstance(session_id, str) and len(session_id) >= 8

    stats_resp = client.post("/api/session/stats", json={"session_id": session_id})
    assert stats_resp.status_code == 200
    data = stats_resp.json()
    assert data["session_id"] == session_id
    assert data["company_chunks"] == 0


def test_analyze_text_requires_company_documents() -> None:
    create_resp = client.post("/api/session")
    session_id = create_resp.json()["session_id"]

    analyze_resp = client.post(
        "/api/analyze/text",
        json={"session_id": session_id, "document_text": "테스트 문서"},
    )
    assert analyze_resp.status_code == 400
    assert "회사 문서를 먼저 업로드" in analyze_resp.json()["detail"]


@pytest.mark.skip(reason="Tool Use: off-topic now handled by LLM general_response, not blocked")
def test_chat_blocks_offtopic_without_context() -> None:
    create_resp = client.post("/api/session")
    session_id = create_resp.json()["session_id"]

    chat_resp = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "배고파"},
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert data["blocked"] is True
    assert data["policy"] == "BLOCK_OFFTOPIC"
    assert "입찰/RFx 문서 분석 전용" in data["answer"]


def test_chat_blocks_unsafe_keywords() -> None:
    """UNSAFE 키워드는 LLM 호출 없이 즉시 차단."""
    create_resp = client.post("/api/session")
    assert create_resp.status_code == 200
    sid = create_resp.json()["session_id"]

    resp = client.post(
        "/api/chat",
        json={"session_id": sid, "message": "해킹 방법 알려줘"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked"] is True
    assert data["policy"] == "BLOCK_UNSAFE"
    assert "안전 정책" in data["answer"]


def test_chat_quota_blocks_when_daily_limit_exceeded(monkeypatch) -> None:
    monkeypatch.setenv("QUOTA_ENABLED", "1")
    monkeypatch.setenv("QUOTA_CHAT_DAILY_LIMIT", "1")
    monkeypatch.setenv("QUOTA_CHAT_MONTHLY_LIMIT", "0")

    create_resp = client.post("/api/session")
    session_id = create_resp.json()["session_id"]

    first = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "배고파"},
    )
    assert first.status_code == 200
    assert first.json().get("quota", {}).get("today_used", 0) >= 1

    second = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "점심 뭐 먹지"},
    )
    assert second.status_code == 429
    payload = second.json()
    assert payload["detail"]["reason"] == "DAILY_LIMIT_EXCEEDED"


def test_usage_me_returns_today_and_month_counts(monkeypatch) -> None:
    monkeypatch.setenv("QUOTA_ENABLED", "1")
    monkeypatch.setenv("QUOTA_CHAT_DAILY_LIMIT", "20")
    monkeypatch.setenv("QUOTA_CHAT_MONTHLY_LIMIT", "0")

    create_resp = client.post("/api/session")
    session_id = create_resp.json()["session_id"]
    client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "배고파"},
    )

    usage_resp = client.post("/api/usage/me", json={"session_id": session_id})
    assert usage_resp.status_code == 200
    usage = usage_resp.json()
    assert usage["ok"] is True
    assert usage["chat"]["today_used"] >= 1
    assert usage["chat"]["month_used"] >= 1


def test_auth_me_returns_unauthenticated_without_cookie() -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["authenticated"] is False
    assert payload["user"] is None


def test_google_login_redirects_to_google_auth(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8010/auth/google/callback")
    resp = client.get("/auth/google/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    assert "accounts.google.com" in location
    assert "client_id=test_client_id" in location


def test_google_callback_sets_session_cookie_and_auth_me(monkeypatch) -> None:
    from services.web_app import main as web_main

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8010/auth/google/callback")
    monkeypatch.setenv("GOOGLE_OAUTH_POST_LOGIN_URL", "http://localhost:3000/")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "0")

    monkeypatch.setattr(
        web_main,
        "_exchange_google_code_for_token",
        lambda code: {"access_token": "fake_access_token"},
    )
    monkeypatch.setattr(
        web_main,
        "_fetch_google_userinfo",
        lambda access_token: {
            "sub": "google-sub-001",
            "email": "e2e@example.com",
            "name": "E2E User",
        },
    )

    login_resp = client.get("/auth/google/login", follow_redirects=False)
    assert login_resp.status_code in (302, 307)
    location = login_resp.headers.get("location", "")
    parsed = urllib.parse.urlparse(location)
    state = urllib.parse.parse_qs(parsed.query).get("state", [""])[0]
    assert state

    callback_resp = client.get(
        "/auth/google/callback",
        params={"code": "fake_code", "state": state},
        follow_redirects=False,
    )
    assert callback_resp.status_code in (302, 307)
    assert callback_resp.headers.get("location", "").startswith("http://localhost:3000/")
    set_cookie = callback_resp.headers.get("set-cookie", "")
    assert "kira_auth=" in set_cookie

    me_resp = client.get("/auth/me")
    assert me_resp.status_code == 200
    payload = me_resp.json()
    assert payload["authenticated"] is True
    assert payload["user"]["email"] == "e2e@example.com"


def test_chat_gap_query_returns_no_gap_when_latest_matching_is_all_met(monkeypatch) -> None:
    monkeypatch.setattr(
        web_main,
        "apply_context_policy",
        lambda decision, has_context, relevance_score, min_relevance_score: decision,
    )

    create_resp = client.post("/api/session")
    session_id = create_resp.json()["session_id"]
    session = web_main.SESSIONS[session_id]

    req = RFxRequirement(category="자격", description="ISO 9001 보유", is_mandatory=True, detail="")
    match = RequirementMatch(
        requirement=req,
        status=MatchStatus.MET,
        evidence="회사 문서에서 ISO 9001 인증서 확인",
        confidence=0.95,
        preparation_guide="",
        source_files=["company_profile.pdf"],
    )
    session.latest_matching_result = MatchingResult(
        overall_score=100.0,
        recommendation="🟢 GO - 적극 참여 권장",
        matches=[match],
    )

    chat_resp = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "입찰 참여에 부족한거 찾아줘"},
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert data["blocked"] is False
    assert "latest_matching_guard" in data["reason"]
    assert "미충족/보완 필요 항목이 없습니다" in data["answer"]


def test_chat_gap_query_returns_gap_list_when_latest_matching_has_issues(monkeypatch) -> None:
    monkeypatch.setattr(
        web_main,
        "apply_context_policy",
        lambda decision, has_context, relevance_score, min_relevance_score: decision,
    )

    create_resp = client.post("/api/session")
    session_id = create_resp.json()["session_id"]
    session = web_main.SESSIONS[session_id]

    req = RFxRequirement(category="실적", description="최근 3년 20억 이상 2건", is_mandatory=True, detail="")
    issue_match = RequirementMatch(
        requirement=req,
        status=MatchStatus.NOT_MET,
        evidence="요건에 해당하는 실적 2건 확인 불가",
        confidence=0.9,
        preparation_guide="최근 3년 실적증명서 2건을 보완 제출하세요.",
        source_files=["company_profile.pdf"],
    )
    session.latest_matching_result = MatchingResult(
        overall_score=62.0,
        recommendation="🟡 CONDITIONAL - 필수 요건 1개 증빙 확인 필요",
        matches=[issue_match],
    )

    chat_resp = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "입찰 참여 조건이 부족한 부분 찾아줘"},
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert data["blocked"] is False
    assert "latest_matching_guard" in data["reason"]
    assert "보완 필요 항목입니다" in data["answer"]
    assert "필수/미충족" in data["answer"]
    assert "최근 3년 실적증명서 2건을 보완 제출하세요." in data["answer"]


def test_get_alert_config_nonexistent_returns_default():
    """GET /api/alerts/config for new user returns default config"""
    resp = client.get("/api/alerts/config?email=new@example.com")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["enabled"] is False
    assert data["rules"] == []


def test_save_and_retrieve_alert_config():
    """POST /api/alerts/config saves and GET retrieves"""
    config = {
        "email": "user@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9, 18],
        "rules": [{
            "id": "1",
            "keywords": ["교통신호등"],
            "excludeRegions": ["안산"],
            "productCodes": ["42101"],
            "enabled": True,
        }],
        "companyProfile": {
            "description": "교통신호등 제조 전문",
        }
    }

    # Save
    save_resp = client.post("/api/alerts/config", json=config)
    assert save_resp.status_code == 200
    assert save_resp.json()["success"] is True

    # Retrieve
    get_resp = client.get("/api/alerts/config?email=user@example.com")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["email"] == "user@example.com"
    assert data["schedule"] == "daily_2"
    assert len(data["rules"]) == 1
    assert data["rules"][0]["excludeRegions"] == ["안산"]
    assert data["companyProfile"]["description"] == "교통신호등 제조 전문"


def test_save_alert_config_validates_email():
    """POST /api/alerts/config rejects invalid email"""
    config = {
        "email": "invalid-email",
        "enabled": True,
        "rules": []
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "유효한 이메일" in resp.json()["detail"]


def test_alert_config_full_workflow():
    """Full workflow: create config with all filters, retrieve, verify"""
    config = {
        "email": "integration@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9, 18],
        "companyProfile": {
            "description": "교통신호등 제조 전문. ISO 9001 보유.",
            "mainProducts": ["교통신호등", "CCTV"],
            "excludedAreas": ["안산", "부산"],
        },
        "rules": [
            {
                "id": "rule1",
                "keywords": ["교통신호등", "CCTV"],
                "excludeKeywords": ["유지보수"],
                "categories": ["물품"],
                "regions": ["서울", "경기"],
                "excludeRegions": ["안산"],
                "productCodes": ["42101", "42105"],
                "detailedItems": ["교통신호등 주"],
                "minAmt": 50000000,
                "maxAmt": 200000000,
                "enabled": True,
            }
        ],
    }

    # Save
    save_resp = client.post("/api/alerts/config", json=config)
    assert save_resp.status_code == 200

    # Retrieve
    get_resp = client.get("/api/alerts/config?email=integration@example.com")
    assert get_resp.status_code == 200

    data = get_resp.json()

    # Top-level fields
    assert data["email"] == "integration@example.com"
    assert data["enabled"] is True
    assert data["schedule"] == "daily_2"
    assert data["hours"] == [9, 18]

    # Company profile
    profile = data["companyProfile"]
    assert profile["description"] == "교통신호등 제조 전문. ISO 9001 보유."
    assert profile["mainProducts"] == ["교통신호등", "CCTV"]
    assert profile["excludedAreas"] == ["안산", "부산"]

    # Rules[0] - all fields
    rule = data["rules"][0]
    assert rule["id"] == "rule1"
    assert rule["keywords"] == ["교통신호등", "CCTV"]
    assert rule["excludeKeywords"] == ["유지보수"]
    assert rule["categories"] == ["물품"]
    assert rule["regions"] == ["서울", "경기"]
    assert rule["excludeRegions"] == ["안산"]
    assert rule["productCodes"] == ["42101", "42105"]
    assert rule["detailedItems"] == ["교통신호등 주"]
    assert rule["minAmt"] == 50000000
    assert rule["maxAmt"] == 200000000
    assert rule["enabled"] is True


def test_save_alert_config_rejects_empty_keywords():
    """Rules with empty keywords should be rejected"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9],
        "rules": [{"id": "1", "keywords": [], "enabled": True}],
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "키워드" in resp.json()["detail"]


def test_save_alert_config_rejects_invalid_schedule():
    """Invalid schedule value should be rejected"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "invalid_schedule",
        "hours": [],
        "rules": [],
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "schedule" in resp.json()["detail"]


def test_save_alert_config_rejects_too_many_keywords():
    """Rules with more than 50 keywords should be rejected"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_1",
        "hours": [],
        "rules": [{"id": "1", "keywords": [f"keyword{i}" for i in range(51)], "enabled": True}],
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "키워드" in resp.json()["detail"]
    assert "50" in resp.json()["detail"]


def test_save_alert_config_rejects_invalid_hours_type():
    """Hours field must be a list"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": "not-a-list",
        "rules": [],
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "hours" in resp.json()["detail"]
    assert "배열" in resp.json()["detail"]


def test_save_alert_config_accepts_valid_rules():
    """Valid rules with 1-50 keywords should be accepted"""
    config = {
        "email": "valid@example.com",
        "enabled": True,
        "schedule": "daily_1",
        "hours": [9],
        "rules": [
            {"id": "1", "keywords": ["keyword1"], "enabled": True},
            {"id": "2", "keywords": [f"kw{i}" for i in range(50)], "enabled": True},
        ],
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_save_alert_config_rejects_non_list_keywords():
    """Keywords must be a list, not a string"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9],
        "rules": [{"id": "1", "keywords": "not-a-list", "enabled": True}],
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "keywords" in resp.json()["detail"]
    assert "배열" in resp.json()["detail"]


def test_save_alert_config_rejects_non_dict_company_profile():
    """companyProfile must be a dict, not a string"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9],
        "rules": [],
        "companyProfile": "not-a-dict",
    }

    resp = client.post("/api/alerts/config", json=config)
    assert resp.status_code == 400
    assert "companyProfile" in resp.json()["detail"]
