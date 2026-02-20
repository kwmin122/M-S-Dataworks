from pathlib import Path
import urllib.parse
import sys

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
