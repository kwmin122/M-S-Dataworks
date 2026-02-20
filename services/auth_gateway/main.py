"""
Kira Auth Gateway (FastAPI)

역할:
1) Supabase OAuth access token을 POST body로 교환
2) Supabase JWT(JWKS) 검증
3) 내부 세션 발급 + HttpOnly 쿠키 설정
4) 로그아웃 시 내부 세션/쿠키 무효화
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jwt import PyJWKClient
from pydantic import BaseModel


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from user_store import (  # noqa: E402
    create_user_session,
    init_user_store,
    invalidate_user_session,
    upsert_social_user,
)


app = FastAPI(title="Kira Auth Gateway", version="0.1.0")
init_user_store()

_jwk_client: PyJWKClient | None = None


class ExchangeRequest(BaseModel):
    access_token: str
    provider: str = "unknown"
    redirect_path: str = "/tool"


def _safe_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return int(default)


def _safe_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "off", "no"}


def _auth_cookie_name() -> str:
    return os.getenv("AUTH_COOKIE_NAME", "kira_auth").strip() or "kira_auth"


def _auth_cookie_path() -> str:
    path = os.getenv("AUTH_COOKIE_PATH", "/").strip()
    if not path.startswith("/"):
        return "/"
    return path


def _auth_cookie_domain() -> str | None:
    domain = os.getenv("AUTH_COOKIE_DOMAIN", "").strip()
    return domain or None


def _allowed_algorithms() -> set[str]:
    raw = os.getenv("SUPABASE_ALLOWED_ALGORITHMS", "RS256").strip()
    return {item.strip() for item in raw.split(",") if item.strip()} or {"RS256"}


def _allowed_redirect_paths() -> list[str]:
    raw = os.getenv("SOCIAL_AUTH_ALLOWED_REDIRECTS", "/tool,/").strip()
    candidates = [item.strip() for item in raw.split(",") if item.strip()]
    normalized: list[str] = []
    for candidate in candidates:
        if not candidate.startswith("/"):
            continue
        if "://" in candidate or candidate.startswith("//"):
            continue
        normalized.append(candidate)
    if not normalized:
        normalized = ["/tool", "/"]
    return normalized


def _validate_redirect_path(path: str) -> str:
    candidate = (path or "/tool").strip()
    if not candidate.startswith("/") or "://" in candidate or candidate.startswith("//"):
        raise HTTPException(status_code=400, detail="Invalid redirect path")

    allowed = _allowed_redirect_paths()
    for prefix in allowed:
        if prefix == "/" and candidate == "/":
            return candidate
        normalized_prefix = prefix.rstrip("/")
        if not normalized_prefix:
            normalized_prefix = "/"
        if candidate == normalized_prefix or candidate.startswith(f"{normalized_prefix}/"):
            return candidate
    raise HTTPException(status_code=400, detail="Redirect path is not in allowlist")


def _jwk() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is not None:
        return _jwk_client
    jwks_url = os.getenv("SUPABASE_JWKS_URL", "").strip()
    if not jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL is not configured")
    _jwk_client = PyJWKClient(jwks_url)
    return _jwk_client


def _decode_supabase_token(access_token: str) -> dict[str, Any]:
    token = (access_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="access_token is required")

    issuer = os.getenv("SUPABASE_ISSUER", "").strip()
    audience = os.getenv("SUPABASE_AUDIENCE", "").strip()
    if not issuer:
        raise RuntimeError("SUPABASE_ISSUER is not configured")

    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token header: {exc}") from exc

    alg = str(header.get("alg", "")).strip()
    if alg not in _allowed_algorithms():
        raise HTTPException(status_code=401, detail=f"Disallowed JWT algorithm: {alg}")

    try:
        signing_key = _jwk().get_signing_key_from_jwt(token).key
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Unable to resolve signing key: {exc}") from exc

    decode_kwargs: dict[str, Any] = {
        "jwt": token,
        "key": signing_key,
        "algorithms": [alg],
        "issuer": issuer,
        "options": {
            "require": ["exp", "sub"],
            "verify_aud": bool(audience),
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
        },
    }
    if audience:
        decode_kwargs["audience"] = audience

    try:
        claims = jwt.decode(**decode_kwargs)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {exc}") from exc

    if str(claims.get("iss", "")) != issuer:
        raise HTTPException(status_code=401, detail="Issuer mismatch")

    return claims


def _provider_from_claims(claims: dict[str, Any], fallback_provider: str) -> str:
    app_meta = claims.get("app_metadata", {})
    provider = ""
    if isinstance(app_meta, dict):
        provider = str(app_meta.get("provider", "")).strip().lower()
    if not provider:
        provider = str(claims.get("provider", "")).strip().lower()
    if not provider:
        provider = str(fallback_provider or "unknown").strip().lower()
    if provider not in {"google", "kakao"}:
        provider = "unknown"
    return provider


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"ok": "true", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/auth/session/exchange")
def exchange_session(payload: ExchangeRequest) -> JSONResponse:
    claims = _decode_supabase_token(payload.access_token)
    provider = _provider_from_claims(claims, payload.provider)
    external_sub = str(claims.get("sub", "")).strip()
    if not external_sub:
        raise HTTPException(status_code=401, detail="Token subject(sub) missing")

    email = str(claims.get("email", "")).strip().lower()
    user_meta = claims.get("user_metadata", {})
    display_name = ""
    if isinstance(user_meta, dict):
        display_name = str(
            user_meta.get("name")
            or user_meta.get("full_name")
            or user_meta.get("nickname")
            or ""
        ).strip()

    username = upsert_social_user(
        provider=provider,
        external_sub=external_sub,
        email=email,
        display_name=display_name,
    )

    ttl_days = max(1, _safe_int_env("AUTH_SESSION_TTL_DAYS", 7))
    session_token = create_user_session(username=username, ttl_days=ttl_days)
    redirect_path = _validate_redirect_path(payload.redirect_path)

    response = JSONResponse(
        {
            "ok": True,
            "username": username,
            "redirect_path": redirect_path,
            "provider": provider,
        }
    )
    response.set_cookie(
        key=_auth_cookie_name(),
        value=session_token,
        httponly=True,
        secure=_safe_bool_env("AUTH_COOKIE_SECURE", True),
        samesite="lax",
        path=_auth_cookie_path(),
        domain=_auth_cookie_domain(),
        max_age=ttl_days * 24 * 60 * 60,
    )
    return response


@app.post("/auth/logout")
def logout(request: Request) -> JSONResponse:
    token = request.cookies.get(_auth_cookie_name(), "")
    if token:
        invalidate_user_session(token)

    response = JSONResponse({"ok": True})
    response.delete_cookie(
        key=_auth_cookie_name(),
        path=_auth_cookie_path(),
        domain=_auth_cookie_domain(),
    )
    return response


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("AUTH_GATEWAY_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = _safe_int_env("AUTH_GATEWAY_PORT", 8008)
    uvicorn.run("main:app", host=host, port=port, reload=False)

