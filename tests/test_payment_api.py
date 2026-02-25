"""결제 / 구독 API 테스트."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.web_app.main import (
    _BILLING_KEY_RE,
    _safe_username_for_path,
    _SUBSCRIPTIONS_DIR,
    app,
)

client = TestClient(app)

# ── 헬퍼 ──

_TEST_USERNAME = "test-payment-user@example.com"
_TEST_TOKEN = "test-payment-session-token"


def _auth_cookie() -> dict[str, str]:
    """테스트용 인증 쿠키."""
    return {"kira_auth": _TEST_TOKEN}


def _cleanup_sub():
    """테스트 구독 파일 정리."""
    safe = _safe_username_for_path(_TEST_USERNAME)
    path = _SUBSCRIPTIONS_DIR / f"{safe}.json"
    if path.exists():
        path.unlink()


@pytest.fixture(autouse=True)
def _setup_teardown():
    """각 테스트 전후 정리."""
    _cleanup_sub()
    yield
    _cleanup_sub()


# ── _safe_username_for_path 단위 테스트 ──


class TestSafeUsername:
    def test_normal_email(self):
        assert _safe_username_for_path("user@example.com") == "user@example.com"

    def test_slashes_replaced(self):
        result = _safe_username_for_path("user/../../etc/passwd")
        assert "/" not in result
        assert ".." not in result

    def test_backslash_replaced(self):
        result = _safe_username_for_path("user\\..\\etc")
        assert "\\" not in result

    def test_null_byte_replaced(self):
        result = _safe_username_for_path("user\x00evil")
        assert "\x00" not in result

    def test_leading_dot_stripped(self):
        result = _safe_username_for_path(".hidden")
        assert not result.startswith(".")

    def test_length_capped(self):
        long_name = "a" * 500
        result = _safe_username_for_path(long_name)
        assert len(result) <= 100


# ── 인증 필수 테스트 ──


class TestAuthRequired:
    def test_subscription_get_requires_auth(self):
        resp = client.get("/api/payments/subscription")
        assert resp.status_code == 401

    def test_billing_key_requires_auth(self):
        resp = client.post(
            "/api/payments/billing-key",
            json={"billingKey": "bk_test", "plan": "pro", "cardLast4": "1234"},
        )
        assert resp.status_code == 401

    def test_cancel_requires_auth(self):
        resp = client.post("/api/payments/cancel", json={})
        assert resp.status_code == 401

    def test_verify_amount_requires_auth(self):
        resp = client.post(
            "/api/payments/verify-amount", json={"plan": "pro"}
        )
        assert resp.status_code == 401


# ── 금액 검증 테스트 ──


class TestVerifyAmount:
    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    def test_valid_plan(self, _mock):
        resp = client.post(
            "/api/payments/verify-amount",
            json={"plan": "pro"},
            cookies=_auth_cookie(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == 99_000
        assert data["currency"] == "KRW"

    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    def test_invalid_plan_rejected(self, _mock):
        resp = client.post(
            "/api/payments/verify-amount",
            json={"plan": "platinum"},
            cookies=_auth_cookie(),
        )
        assert resp.status_code == 400


# ── 빌링키 등록 테스트 ──


class TestBillingKey:
    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    def test_empty_billing_key_rejected(self, _mock):
        resp = client.post(
            "/api/payments/billing-key",
            json={"billingKey": "", "plan": "pro", "cardLast4": "1234"},
            cookies=_auth_cookie(),
        )
        assert resp.status_code == 400

    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    def test_free_plan_rejected(self, _mock):
        resp = client.post(
            "/api/payments/billing-key",
            json={"billingKey": "bk_test", "plan": "free", "cardLast4": ""},
            cookies=_auth_cookie(),
        )
        assert resp.status_code == 400

    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    @patch(
        "services.web_app.main._verify_billing_key_with_portone",
        new_callable=AsyncMock,
        return_value=True,
    )
    def test_successful_registration(self, _mock_portone, _mock_auth):
        resp = client.post(
            "/api/payments/billing-key",
            json={"billingKey": "bk_test_123", "plan": "pro", "cardLast4": "4242"},
            cookies=_auth_cookie(),
        )
        assert resp.status_code == 200
        sub = resp.json()["subscription"]
        assert sub["plan"] == "pro"
        assert sub["status"] == "active"
        assert sub["priceKrw"] == 99_000
        # billingKey가 응답에 포함되지 않아야 함 (보안)
        assert "billingKey" not in sub

    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    @patch(
        "services.web_app.main._verify_billing_key_with_portone",
        new_callable=AsyncMock,
        return_value=True,
    )
    def test_duplicate_active_subscription_returns_existing(self, _mock_portone, _mock_auth):
        # 첫 등록
        client.post(
            "/api/payments/billing-key",
            json={"billingKey": "bk_test_1", "plan": "pro", "cardLast4": "4242"},
            cookies=_auth_cookie(),
        )
        # 중복 등록 시도
        resp = client.post(
            "/api/payments/billing-key",
            json={"billingKey": "bk_test_2", "plan": "pro", "cardLast4": "4242"},
            cookies=_auth_cookie(),
        )
        assert resp.status_code == 200
        assert "이미 동일 플랜" in resp.json().get("message", "")

    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    @patch(
        "services.web_app.main._verify_billing_key_with_portone",
        new_callable=AsyncMock,
        return_value=False,
    )
    def test_invalid_billing_key_rejected(self, _mock_portone, _mock_auth):
        resp = client.post(
            "/api/payments/billing-key",
            json={"billingKey": "fake_key", "plan": "pro", "cardLast4": "0000"},
            cookies=_auth_cookie(),
        )
        assert resp.status_code == 400
        assert "유효하지 않은 빌링키" in resp.json()["detail"]


# ── 구독 조회 테스트 ──


class TestGetSubscription:
    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    def test_no_subscription_returns_free(self, _mock):
        resp = client.get(
            "/api/payments/subscription", cookies=_auth_cookie()
        )
        assert resp.status_code == 200
        sub = resp.json()["subscription"]
        assert sub["plan"] == "free"
        assert sub["status"] == "none"

    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    @patch(
        "services.web_app.main._verify_billing_key_with_portone",
        new_callable=AsyncMock,
        return_value=True,
    )
    def test_active_subscription_hides_billing_key(self, _mock_portone, _mock_auth):
        # 먼저 등록
        client.post(
            "/api/payments/billing-key",
            json={"billingKey": "bk_secret", "plan": "pro", "cardLast4": "1234"},
            cookies=_auth_cookie(),
        )
        # 조회
        resp = client.get(
            "/api/payments/subscription", cookies=_auth_cookie()
        )
        sub = resp.json()["subscription"]
        assert sub["plan"] == "pro"
        assert "billingKey" not in sub


# ── 구독 해지 테스트 ──


class TestCancelSubscription:
    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    def test_cancel_without_subscription_fails(self, _mock):
        resp = client.post(
            "/api/payments/cancel", json={}, cookies=_auth_cookie()
        )
        assert resp.status_code == 400

    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    @patch(
        "services.web_app.main._verify_billing_key_with_portone",
        new_callable=AsyncMock,
        return_value=True,
    )
    def test_cancel_active_subscription(self, _mock_portone, _mock_auth):
        # 먼저 등록
        client.post(
            "/api/payments/billing-key",
            json={"billingKey": "bk_cancel_test", "plan": "pro", "cardLast4": "5678"},
            cookies=_auth_cookie(),
        )
        # 해지
        resp = client.post(
            "/api/payments/cancel", json={}, cookies=_auth_cookie()
        )
        assert resp.status_code == 200
        sub = resp.json()["subscription"]
        assert sub["status"] == "cancelled"
        assert sub["cancelledAt"] is not None
        assert "billingKey" not in sub


# ── 웹훅 테스트 ──


class TestWebhook:
    def test_webhook_without_secret_returns_503(self):
        """PORTONE_WEBHOOK_SECRET 미설정 시 503."""
        with patch.dict("os.environ", {"PORTONE_WEBHOOK_SECRET": ""}, clear=False):
            resp = client.post(
                "/api/payments/webhook",
                json={"type": "Transaction.Paid"},
            )
            assert resp.status_code == 503

    def test_webhook_missing_headers_returns_401(self):
        """서명 헤더 누락 시 401."""
        with patch.dict(
            "os.environ", {"PORTONE_WEBHOOK_SECRET": "whsec_dGVzdHNlY3JldA=="}, clear=False
        ):
            resp = client.post(
                "/api/payments/webhook",
                json={"type": "Transaction.Paid"},
            )
            assert resp.status_code == 401

    def test_webhook_invalid_signature_returns_401(self):
        """잘못된 서명 시 401."""
        wh_ts = str(int(time.time()))
        with patch.dict(
            "os.environ", {"PORTONE_WEBHOOK_SECRET": "whsec_dGVzdHNlY3JldA=="}, clear=False
        ):
            resp = client.post(
                "/api/payments/webhook",
                json={"type": "Transaction.Paid"},
                headers={
                    "webhook-id": "msg_test",
                    "webhook-timestamp": wh_ts,
                    "webhook-signature": "v1,invalidsignature",
                },
            )
            assert resp.status_code == 401

    def test_webhook_valid_signature_succeeds(self):
        """올바른 Svix 서명 시 200."""
        secret_b64 = base64.b64encode(b"testsecret").decode()
        env_secret = f"whsec_{secret_b64}"
        body_str = json.dumps({"type": "Transaction.Paid"})

        wh_id = "msg_test_123"
        wh_ts = str(int(time.time()))
        signed_payload = f"{wh_id}.{wh_ts}.{body_str}".encode()
        expected = base64.b64encode(
            hmac.new(b"testsecret", signed_payload, hashlib.sha256).digest()
        ).decode()
        wh_sig = f"v1,{expected}"

        with patch.dict("os.environ", {"PORTONE_WEBHOOK_SECRET": env_secret}, clear=False):
            resp = client.post(
                "/api/payments/webhook",
                content=body_str,
                headers={
                    "Content-Type": "application/json",
                    "webhook-id": wh_id,
                    "webhook-timestamp": wh_ts,
                    "webhook-signature": wh_sig,
                },
            )
            assert resp.status_code == 200

    def test_webhook_old_timestamp_rejected(self):
        """5분 초과 타임스탬프 시 401."""
        with patch.dict(
            "os.environ", {"PORTONE_WEBHOOK_SECRET": "whsec_dGVzdHNlY3JldA=="}, clear=False
        ):
            resp = client.post(
                "/api/payments/webhook",
                json={"type": "Transaction.Paid"},
                headers={
                    "webhook-id": "msg_test",
                    "webhook-timestamp": "1234567890",
                    "webhook-signature": "v1,anything",
                },
            )
            assert resp.status_code == 401
            assert "out of range" in resp.json()["detail"]


# ── 빌링키 형식 검증 테스트 ──


class TestBillingKeyFormat:
    def test_valid_format(self):
        assert _BILLING_KEY_RE.match("billing-key-abcde12345")

    def test_valid_format_with_hyphens(self):
        assert _BILLING_KEY_RE.match("billing-key-abc-def-12345678")

    def test_invalid_prefix(self):
        assert not _BILLING_KEY_RE.match("bk_test_123")

    def test_path_traversal_rejected(self):
        assert not _BILLING_KEY_RE.match("billing-key-../../../etc/passwd")

    def test_too_short(self):
        assert not _BILLING_KEY_RE.match("billing-key-abc")

    def test_empty(self):
        assert not _BILLING_KEY_RE.match("")

    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    def test_bad_format_billing_key_returns_400(self, _mock_auth):
        """빌링키 형식이 잘못된 경우 _verify가 False 반환 → 400."""
        with patch.dict("os.environ", {"PORTONE_API_SECRET": "test_secret"}, clear=False):
            resp = client.post(
                "/api/payments/billing-key",
                json={"billingKey": "bk_invalid_format", "plan": "pro", "cardLast4": "1234"},
                cookies=_auth_cookie(),
            )
            assert resp.status_code == 400
            assert "유효하지 않은 빌링키" in resp.json()["detail"]

    @patch("services.web_app.main.resolve_user_from_session", return_value=_TEST_USERNAME)
    def test_portone_secret_missing_returns_503(self, _mock_auth):
        """PORTONE_API_SECRET 미설정 시 503."""
        with patch.dict("os.environ", {"PORTONE_API_SECRET": ""}, clear=False):
            resp = client.post(
                "/api/payments/billing-key",
                json={
                    "billingKey": "billing-key-validtest1234",
                    "plan": "pro",
                    "cardLast4": "1234",
                },
                cookies=_auth_cookie(),
            )
            assert resp.status_code == 503
