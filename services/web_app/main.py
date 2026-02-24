"""
Kira Web Runtime API

Streamlit UI 없이 웹 랜딩(index.html)에서 Kira 분석 엔진을 직접 실행하기 위한 API 서버.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
_WEB_APP_DIR = str(Path(__file__).resolve().parent)
if _WEB_APP_DIR not in sys.path:
    sys.path.insert(0, _WEB_APP_DIR)

load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)

from engine import RAGEngine  # noqa: E402
from nara_api import (  # noqa: E402
    search_bids as nara_search_bids,
    get_bid_detail_attachments as nara_get_bid_detail_attachments,
    get_bid_attachments as nara_get_bid_attachments,
    download_attachment as nara_download_attachment,
    pick_best_attachment,
)
from matcher import MatchStatus, MatchingResult, QualificationMatcher  # noqa: E402
from rfx_analyzer import RFxAnalysisResult, RFxAnalyzer  # noqa: E402
from document_parser import DocumentParser  # noqa: E402
from chat_router import (  # noqa: E402
    ChatPolicy,
    apply_context_policy,
    build_policy_response,
    default_router_log_path,
    route_user_query,
    write_router_telemetry,
)
from user_store import (  # noqa: E402
    create_user_session,
    enforce_usage_quota,
    get_actor_usage_counts,
    get_usage_overview,
    list_usage_by_actor,
    get_user_profile,
    init_user_store,
    invalidate_user_session,
    resolve_user_from_session,
    upsert_social_user,
    username_to_scope,
)


ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt",
    ".hwp", ".hwpx",
    ".xlsx", ".xls", ".csv",
    ".pptx", ".ppt",
}
DEFAULT_SESSION_TTL_HOURS = 12
FRONTEND_DIR = ROOT_DIR / "frontend" / "kirabot"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
CHAT_RESPONSE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {"type": "string"},
        "references": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "page": {"type": "integer", "minimum": 1},
                    "text": {"type": "string"},
                },
                "required": ["page", "text"],
            },
        },
    },
    "required": ["answer", "references"],
}

QUESTION_HINT_KEYWORDS: tuple[str, ...] = (
    "요건",
    "자격",
    "평가",
    "근거",
    "문서",
    "공고",
    "입찰",
    "rfx",
    "rfp",
    "준비",
    "체크리스트",
    "미충족",
    "가점",
    "마감",
    "회사",
)

GENERIC_QUESTION_PATTERNS: tuple[str, ...] = (
    "업무와 관련된 질문",
    "최근 프로젝트",
    "이야기해볼까요",
    "무엇을 도와",
    "도움이 필요",
)

GAP_QUERY_KEYWORDS: tuple[str, ...] = (
    "부족",
    "미충족",
    "모자",
    "불충분",
    "결격",
    "참여하기엔",
    "안되는 이유",
    "왜 안",
    "리스크",
    "보완",
)

DEFAULT_SUGGESTIONS_NO_CONTEXT: list[str] = [
    "회사 소개서 PDF를 먼저 올리면 어떤 항목을 확인할 수 있어?",
    "분석할 문서를 업로드하면 어떤 결과가 나오는지 알려줘",
    "이 도구로 우리 회사 입찰 준비 시간을 얼마나 줄일 수 있어?",
    "첫 분석 전에 준비할 파일 2가지를 알려줘",
]

DEFAULT_SUGGESTIONS_COMPANY_ONLY: list[str] = [
    "우리 회사 강점 3가지를 문서 근거로 요약해줘",
    "우리 회사 보유 인증/실적 항목을 정리해줘",
    "입찰 준비에 바로 쓸 수 있는 회사 소개 포인트를 뽑아줘",
    "분석할 공고 문서를 올리기 전에 부족한 자료를 점검해줘",
]

DEFAULT_SUGGESTIONS_WITH_ANALYSIS: list[str] = [
    "이 공고 필수요건 중 미충족 항목만 우선순위로 정리해줘",
    "마감일까지 준비해야 할 서류 체크리스트를 만들어줘",
    "근거 페이지와 함께 GO/NO-GO 판단을 짧게 알려줘",
    "점수에 가장 큰 영향을 주는 항목 3개를 알려줘",
]

DEFAULT_SUGGESTIONS_OFFTOPIC: list[str] = [
    "이 공고 필수요건 3개만 먼저 요약해줘",
    "우리 회사 기준으로 미충족 항목을 알려줘",
    "근거 페이지와 함께 핵심 리스크를 정리해줘",
    "마감 전 준비 순서를 체크리스트로 보여줘",
]
OAUTH_STATE_TTL_SECONDS = 600
DEFAULT_CHAT_DAILY_LIMIT = 20
DEFAULT_ANALYZE_MONTHLY_LIMIT = 30


class SessionPayload(BaseModel):
    session_id: str


class AnalyzeTextPayload(BaseModel):
    session_id: str
    document_text: str


class ChatPayload(BaseModel):
    session_id: str
    message: str


class BidSearchPayload(BaseModel):
    keywords: list[str] | str | None = None
    category: str = "all"
    region: str = ""
    minAmt: float | None = None
    maxAmt: float | None = None
    period: str = "1m"
    excludeExpired: bool = True
    page: int = 1
    pageSize: int = 20


class BidAnalyzePayload(BaseModel):
    session_id: str
    bid_ntce_no: str
    bid_ntce_ord: str = "00"
    category: str = ""


class BidEvaluateBatchPayload(BaseModel):
    session_id: str
    bid_ntce_nos: list[str]


class SmartFitScorePayload(BaseModel):
    session_id: str
    bid_notice_id: str = ""
    bid_title: str = ""
    keywords: list[str] = []


@dataclass
class WebRuntimeSession:
    """웹 UI 세션별 RAG 엔진 컨텍스트."""

    session_id: str
    rag_engine: RAGEngine
    rfx_rag_engine: RAGEngine
    created_at: datetime
    last_used_at: datetime
    latest_rfx_analysis: RFxAnalysisResult | None = None
    latest_matching_result: MatchingResult | None = None
    latest_document_name: str = ""


app = FastAPI(title="Kira Web Runtime", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "WEB_API_ALLOW_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080,null",
        ).split(",")
        if origin.strip()
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: dict[str, WebRuntimeSession] = {}
OAUTH_STATES: dict[str, datetime] = {}

init_user_store()

if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="frontend-assets")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _session_ttl() -> timedelta:
    try:
        ttl_hours = int(os.getenv("WEB_SESSION_TTL_HOURS", str(DEFAULT_SESSION_TTL_HOURS)).strip())
    except ValueError:
        ttl_hours = DEFAULT_SESSION_TTL_HOURS
    return timedelta(hours=max(1, ttl_hours))


def _safe_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except ValueError:
        return float(default)


def _safe_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "off", "no"}


def _safe_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return int(default)


def _quota_enabled() -> bool:
    return _safe_bool_env("QUOTA_ENABLED", True)


def _auth_cookie_name() -> str:
    return os.getenv("AUTH_COOKIE_NAME", "kira_auth").strip() or "kira_auth"


def _auth_cookie_path() -> str:
    path = os.getenv("AUTH_COOKIE_PATH", "/").strip()
    return path if path.startswith("/") else "/"


def _auth_cookie_domain() -> str | None:
    value = os.getenv("AUTH_COOKIE_DOMAIN", "").strip()
    return value or None


def _auth_cookie_secure() -> bool:
    return _safe_bool_env("AUTH_COOKIE_SECURE", False)


def _resolve_usage_actor(request: Request, session_id: str) -> tuple[str, str]:
    token = str(request.cookies.get(_auth_cookie_name(), "") or "")
    username = str(resolve_user_from_session(token) or "")
    if username:
        return f"user:{username_to_scope(username)}", username
    return f"anon:{_sanitize_session_id(session_id)}", ""


def _usage_limits_for_action(action: str) -> tuple[int, int]:
    action_norm = str(action or "").strip().lower()
    if action_norm == "chat":
        return (
            max(0, _safe_int_env("QUOTA_CHAT_DAILY_LIMIT", DEFAULT_CHAT_DAILY_LIMIT)),
            max(0, _safe_int_env("QUOTA_CHAT_MONTHLY_LIMIT", 0)),
        )
    if action_norm == "analyze":
        return (
            max(0, _safe_int_env("QUOTA_ANALYZE_DAILY_LIMIT", 0)),
            max(0, _safe_int_env("QUOTA_ANALYZE_MONTHLY_LIMIT", DEFAULT_ANALYZE_MONTHLY_LIMIT)),
        )
    return (0, 0)


def _enforce_quota_or_raise(
    *,
    request: Request,
    session_id: str,
    action: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not _quota_enabled():
        return {
            "enabled": False,
            "action": action,
            "today_used": 0,
            "today_limit": 0,
            "month_used": 0,
            "month_limit": 0,
        }

    actor_key, username = _resolve_usage_actor(request, session_id)
    daily_limit, monthly_limit = _usage_limits_for_action(action)
    decision = enforce_usage_quota(
        actor_key=actor_key,
        username=username,
        action=action,
        daily_limit=daily_limit,
        monthly_limit=monthly_limit,
        metadata=metadata or {},
    )
    decision["enabled"] = True
    if not decision.get("allowed", False):
        detail = {
            "message": "요청 한도를 초과했습니다.",
            "action": action,
            "reason": decision.get("reason", ""),
            "today_used": decision.get("today_used", 0),
            "today_limit": decision.get("today_limit", 0),
            "month_used": decision.get("month_used", 0),
            "month_limit": decision.get("month_limit", 0),
        }
        raise HTTPException(status_code=429, detail=detail)
    return decision


def _admin_usernames() -> set[str]:
    values: set[str] = set()
    for env_name in ("SUPER_ADMIN_USERNAMES", "OPERATOR_USERNAMES", "ADMIN_USERNAMES"):
        raw = os.getenv(env_name, "")
        for item in raw.split(","):
            normalized = item.strip()
            if normalized:
                values.add(normalized)
    return values


def _google_client_id() -> str:
    value = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    if not value:
        raise HTTPException(status_code=503, detail="GOOGLE_OAUTH_CLIENT_ID가 설정되지 않았습니다.")
    return value


def _google_client_secret() -> str:
    value = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not value:
        raise HTTPException(status_code=503, detail="GOOGLE_OAUTH_CLIENT_SECRET이 설정되지 않았습니다.")
    return value


def _google_redirect_uri() -> str:
    value = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    if not value:
        raise HTTPException(status_code=503, detail="GOOGLE_OAUTH_REDIRECT_URI가 설정되지 않았습니다.")
    return value


def _google_auth_url() -> str:
    return os.getenv("GOOGLE_OAUTH_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth").strip()


def _google_token_url() -> str:
    return os.getenv("GOOGLE_OAUTH_TOKEN_URL", "https://oauth2.googleapis.com/token").strip()


def _google_userinfo_url() -> str:
    return os.getenv("GOOGLE_OAUTH_USERINFO_URL", "https://openidconnect.googleapis.com/v1/userinfo").strip()


def _google_scopes() -> str:
    return os.getenv("GOOGLE_OAUTH_SCOPES", "openid email profile").strip() or "openid email profile"


def _google_post_login_url() -> str:
    return os.getenv("GOOGLE_OAUTH_POST_LOGIN_URL", "http://localhost:3000/").strip() or "http://localhost:3000/"


def _cleanup_oauth_states() -> None:
    now = _utc_now()
    expired = [state for state, expires_at in OAUTH_STATES.items() if expires_at <= now]
    for state in expired:
        OAUTH_STATES.pop(state, None)


def _register_oauth_state() -> str:
    _cleanup_oauth_states()
    state = secrets.token_urlsafe(24)
    OAUTH_STATES[state] = _utc_now() + timedelta(seconds=OAUTH_STATE_TTL_SECONDS)
    return state


def _validate_oauth_state(state: str) -> None:
    _cleanup_oauth_states()
    state_norm = (state or "").strip()
    expires_at = OAUTH_STATES.pop(state_norm, None)
    if not expires_at:
        raise HTTPException(status_code=400, detail="유효하지 않은 OAuth state입니다.")
    if expires_at <= _utc_now():
        raise HTTPException(status_code=400, detail="만료된 OAuth state입니다.")


def _exchange_google_code_for_token(code: str) -> dict[str, Any]:
    payload = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": _google_client_id(),
            "client_secret": _google_client_secret(),
            "redirect_uri": _google_redirect_uri(),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        _google_token_url(),
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=502, detail=f"Google 토큰 교환 실패: {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google 토큰 교환 오류: {exc}") from exc


def _fetch_google_userinfo(access_token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        _google_userinfo_url(),
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
        payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=502, detail=f"Google 사용자 정보 조회 실패: {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google 사용자 정보 조회 오류: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Google 사용자 정보 응답 형식 오류")
    return payload


def _is_business_suggestion(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if any(pattern in normalized for pattern in GENERIC_QUESTION_PATTERNS):
        return False
    return any(keyword in normalized for keyword in QUESTION_HINT_KEYWORDS)


def _merge_suggestions(primary: list[str], fallback: list[str], limit: int = 4) -> list[str]:
    merged: list[str] = []
    for value in primary + fallback:
        normalized = str(value or "").strip()
        if not normalized or normalized in merged:
            continue
        merged.append(normalized)
        if len(merged) >= limit:
            break
    return merged


def _build_suggested_questions(session: WebRuntimeSession, decision_questions: list[str], blocked_offtopic: bool) -> list[str]:
    if blocked_offtopic:
        base = DEFAULT_SUGGESTIONS_OFFTOPIC
    elif session.latest_matching_result is not None:
        base = DEFAULT_SUGGESTIONS_WITH_ANALYSIS
    elif session.rag_engine.collection.count() > 0:
        base = DEFAULT_SUGGESTIONS_COMPANY_ONLY
    else:
        base = DEFAULT_SUGGESTIONS_NO_CONTEXT

    filtered = [item for item in decision_questions if _is_business_suggestion(item)]
    return _merge_suggestions(filtered, base, limit=4)


def _sanitize_session_id(session_id: str) -> str:
    normalized = str(session_id or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="session_id가 비어 있습니다.")
    if not re.fullmatch(r"[a-z0-9_-]{8,64}", normalized):
        raise HTTPException(status_code=400, detail="session_id 형식이 올바르지 않습니다.")
    return normalized


def _session_collection_name(session_id: str) -> str:
    safe = re.sub(r"[^a-z0-9_]", "_", session_id)
    return f"web_company_{safe[:48]}"


def _session_upload_dir(session_id: str, bucket: str) -> Path:
    base = ROOT_DIR / "data" / "web_uploads" / session_id / bucket
    base.mkdir(parents=True, exist_ok=True)
    return base


def _cleanup_expired_sessions() -> None:
    expired: list[str] = []
    deadline = _utc_now() - _session_ttl()
    for session_id, session in SESSIONS.items():
        if session.last_used_at < deadline:
            expired.append(session_id)

    for session_id in expired:
        session = SESSIONS.pop(session_id, None)
        if not session:
            continue
        try:
            session.rag_engine.clear_collection()
        except Exception:
            pass
        try:
            session.rfx_rag_engine.clear_collection()
        except Exception:
            pass
        upload_root = ROOT_DIR / "data" / "web_uploads" / session_id
        if upload_root.exists():
            shutil.rmtree(upload_root, ignore_errors=True)


def _get_or_create_session(session_id: str) -> WebRuntimeSession:
    _cleanup_expired_sessions()
    normalized = _sanitize_session_id(session_id)

    existing = SESSIONS.get(normalized)
    if existing:
        existing.last_used_at = _utc_now()
        return existing

    rag = RAGEngine(
        persist_directory=str(ROOT_DIR / "data" / "vectordb_web"),
        collection_name=_session_collection_name(normalized),
    )
    rfx_rag = RAGEngine(
        persist_directory=str(ROOT_DIR / "data" / "vectordb_web"),
        collection_name=f"web_rfx_{normalized[:48]}",
    )
    now = _utc_now()
    session = WebRuntimeSession(
        session_id=normalized,
        rag_engine=rag,
        rfx_rag_engine=rfx_rag,
        created_at=now,
        last_used_at=now,
    )
    SESSIONS[normalized] = session
    return session


def _openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY가 설정되지 않았습니다. .env를 확인해주세요.",
        )
    return api_key


def _validate_extension(filename: str) -> None:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다: {ext or '(없음)'}",
        )


async def _save_upload_file(upload_file: UploadFile, target_dir: Path) -> Path:
    filename = upload_file.filename or f"upload_{uuid.uuid4().hex[:8]}"
    _validate_extension(filename)

    safe_name = re.sub(r"[^0-9A-Za-z._\-가-힣]", "_", filename)
    dest = target_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:10]}_{safe_name}"

    data = await upload_file.read()
    dest.write_bytes(data)
    return dest


def _serialize_rfx_analysis(analysis: RFxAnalysisResult) -> dict[str, Any]:
    return {
        "title": analysis.title,
        "issuing_org": analysis.issuing_org,
        "announcement_number": analysis.announcement_number,
        "deadline": analysis.deadline,
        "project_period": analysis.project_period,
        "budget": analysis.budget,
        "document_type": analysis.document_type,
        "is_rfx_like": analysis.is_rfx_like,
        "document_gate_reason": analysis.document_gate_reason,
        "document_gate_confidence": analysis.document_gate_confidence,
        "requirements": [
            {
                "category": req.category,
                "description": req.description,
                "is_mandatory": req.is_mandatory,
                "detail": req.detail,
            }
            for req in analysis.requirements
        ],
        "evaluation_criteria": [
            {
                "category": item.category,
                "item": item.item,
                "score": item.score,
                "detail": item.detail,
            }
            for item in analysis.evaluation_criteria
        ],
        "required_documents": analysis.required_documents,
        "special_notes": analysis.special_notes,
    }


def _serialize_matching_result(result: MatchingResult) -> dict[str, Any]:
    return {
        "overall_score": result.overall_score,
        "recommendation": result.recommendation,
        "summary": result.summary,
        "met_count": result.met_count,
        "partially_met_count": result.partially_met_count,
        "not_met_count": result.not_met_count,
        "unknown_count": result.unknown_count,
        "evaluation": {
            "available": result.evaluation_available,
            "expected_score": result.evaluation_expected_score,
            "total_score": result.evaluation_total_score,
            "technical_expected_score": result.technical_expected_score,
            "price_expected_score": result.price_expected_score,
            "bonus_expected_score": result.bonus_expected_score,
            "notes": result.evaluation_notes,
        },
        "matches": [
            {
                "category": match.requirement.category,
                "description": match.requirement.description,
                "is_mandatory": match.requirement.is_mandatory,
                "status": match.status.value,
                "status_code": {
                    MatchStatus.MET: "MET",
                    MatchStatus.PARTIALLY_MET: "PARTIALLY_MET",
                    MatchStatus.NOT_MET: "NOT_MET",
                    MatchStatus.UNKNOWN: "UNKNOWN",
                }[match.status],
                "confidence": match.confidence,
                "evidence": match.evidence,
                "preparation_guide": match.preparation_guide,
                "source_files": match.source_files,
            }
            for match in result.matches
        ],
        "assistant_opinions": result.assistant_opinions,
        "opinion_mode": result.opinion_mode,
        "report_text": result.to_report(),
    }


def _extract_page_number(source_file: str, metadata: dict[str, Any]) -> int:
    page = int(metadata.get("page_number", -1) or -1)
    if page > 0:
        return page
    match = re.search(r"_p(\d+)$", source_file or "")
    if match:
        return int(match.group(1))
    return -1


def _normalize_ref_text(text: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", text or "").lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _is_grounded_in_rfx(reference: dict[str, Any], rfx_context: str) -> bool:
    page = int(reference.get("page", 0) or 0)
    if page <= 0:
        return False
    snippet = str(reference.get("text", "")).strip()
    if not snippet:
        return True

    snippet_norm = _normalize_ref_text(snippet)
    rfx_norm = _normalize_ref_text(rfx_context)
    if not snippet_norm or not rfx_norm:
        return False
    if snippet_norm in rfx_norm:
        return True
    keywords = [token for token in snippet_norm.split() if len(token) >= 2][:6]
    hit_count = sum(1 for token in keywords if token in rfx_norm)
    return hit_count >= 2


def _collect_rag_scores(session: WebRuntimeSession, message: str) -> tuple[list[float], list[float]]:
    company_scores: list[float] = []
    rfx_scores: list[float] = []

    try:
        if session.rag_engine.collection.count() > 0:
            company_results = session.rag_engine.search(message, top_k=5)
            company_scores = [float(item.score or 0.0) for item in company_results]
    except Exception:
        company_scores = []

    try:
        if session.rfx_rag_engine.collection.count() > 0:
            rfx_results = session.rfx_rag_engine.search(message, top_k=5)
            rfx_scores = [float(item.score or 0.0) for item in rfx_results]
    except Exception:
        rfx_scores = []

    return company_scores, rfx_scores


def _max_relevance_score(company_scores: list[float], rfx_scores: list[float]) -> float:
    all_scores = company_scores + rfx_scores
    if not all_scores:
        return 0.0
    return max(all_scores)


def _looks_like_gap_question(message: str) -> bool:
    normalized = str(message or "").strip().lower()
    if not normalized:
        return False
    return any(token in normalized for token in GAP_QUERY_KEYWORDS)


def _build_gap_answer_from_latest_matching(
    session: WebRuntimeSession,
    message: str,
) -> tuple[str, list[dict[str, Any]]] | None:
    """
    '부족/미충족' 질의는 최신 매칭 결과를 우선 사용해 결정론적으로 응답한다.
    생성형 답변으로 인한 GO/NO-GO 모순을 방지하기 위한 가드 레이어.
    """
    if not _looks_like_gap_question(message):
        return None

    result = session.latest_matching_result
    if result is None:
        return None

    issue_matches = [
        match
        for match in result.matches
        if match.status in {MatchStatus.NOT_MET, MatchStatus.PARTIALLY_MET, MatchStatus.UNKNOWN}
    ]

    if not issue_matches:
        answer = (
            "최근 분석 결과 기준으로는 **미충족/보완 필요 항목이 없습니다.**\n"
            f"- 종합 적합도: {result.overall_score:.0f}%\n"
            f"- 추천: {result.recommendation}\n\n"
            "이전 분석에서 부족 항목이 있었다면, 그때 사용한 문서(회사 문서 또는 공고 문서)가 "
            "현재 분석 대상과 달랐을 가능성이 큽니다. 동일 문서로 다시 분석해 비교해보세요."
        )
        return answer, []

    lines = [
        "최근 분석 결과 기준 보완 필요 항목입니다.",
        f"- 종합 적합도: {result.overall_score:.0f}%",
        f"- 추천: {result.recommendation}",
        "",
    ]
    for idx, match in enumerate(issue_matches[:6], start=1):
        mandatory = "필수" if match.requirement.is_mandatory else "권장"
        guide = (match.preparation_guide or "증빙 자료 보강이 필요합니다.").strip()
        lines.append(
            f"{idx}. [{mandatory}/{match.status.value}] {match.requirement.description}\n"
            f"   - 대응: {guide}"
        )
    return "\n".join(lines), []


def _build_chat_context(session: WebRuntimeSession, message: str) -> tuple[str, str, list[dict[str, Any]]]:
    company_context_text = ""
    rfx_context_text = ""
    fallback_refs: list[dict[str, Any]] = []

    if session.rag_engine.collection.count() > 0:
        for result in session.rag_engine.search(message, top_k=5):
            page_num = _extract_page_number(result.source_file, result.metadata)
            company_context_text += (
                f"\n[회사 출처: {result.source_file}, 페이지 {page_num}]\n{result.text}\n---\n"
            )

    if session.rfx_rag_engine.collection.count() > 0:
        for result in session.rfx_rag_engine.search(message, top_k=5):
            page_num = _extract_page_number(result.source_file, result.metadata)
            rfx_context_text += (
                f"\n[RFx 출처: {result.source_file}, 페이지 {page_num}]\n{result.text}\n---\n"
            )
            if page_num > 0:
                fallback_refs.append(
                    {
                        "page": page_num,
                        "text": str(result.text or "")[:100],
                    }
                )

    return company_context_text, rfx_context_text, fallback_refs


def _generate_chat_answer(
    *,
    api_key: str,
    message: str,
    company_context_text: str,
    rfx_context_text: str,
    session: WebRuntimeSession,
) -> tuple[str, list[dict[str, Any]]]:
    from openai import OpenAI

    matching_context = ""
    if session.latest_matching_result:
        match_result = session.latest_matching_result
        matching_context = (
            f"- 종합 적합도: {match_result.overall_score:.0f}%\n"
            f"- 추천: {match_result.recommendation}\n"
            f"- 충족/부분/미충족: {match_result.met_count}/{match_result.partially_met_count}/{match_result.not_met_count}"
        )

    rfx_context = ""
    if session.latest_rfx_analysis:
        analysis = session.latest_rfx_analysis
        rfx_context = (
            f"- 공고명: {analysis.title}\n"
            f"- 발주기관: {analysis.issuing_org}\n"
            f"- 마감일: {analysis.deadline}\n"
            f"- 문서유형: {analysis.document_type}"
        )

    system_prompt = """당신은 입찰/RFx 문서 분석 보조 어시스턴트입니다.
반드시 JSON 객체로만 응답하세요.
스키마:
{
  "answer": "한국어 답변",
  "references": [
    {"page": 3, "text": "RFx 원문에서 그대로 발췌한 구절"}
  ]
}

규칙:
1) references.page는 RFx 원문 실제 페이지 번호만 사용
2) references.text는 RFx 원문 문구를 그대로 사용 (의역 금지)
3) references는 최대 5개
4) 회사 정보 문구는 references에 넣지 말 것
5) 근거가 부족하면 답변에 부족하다고 명확히 쓸 것
6) 질문이 회사명/인증/실적/강점 등 회사 정보라면 회사 정보 컨텍스트를 우선 사용
7) 회사 정보 기반 답변은 references를 빈 배열로 둘 수 있음
"""

    user_prompt = f"""질문: {message}

[회사 정보 (RAG 검색 결과)]
{company_context_text or '없음'}

[RFx 원문 (RAG 검색 결과)]
{rfx_context_text or '없음'}

[RFx 분석 메타]
{rfx_context or '없음'}

[매칭 요약]
{matching_context or '없음'}
"""

    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        max_tokens=2048,
        temperature=0.3,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "kira_chat_response",
                "strict": True,
                "schema": CHAT_RESPONSE_JSON_SCHEMA,
            },
        },
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    payload = json.loads(content)
    answer = str(payload.get("answer", "")).strip()
    raw_refs = payload.get("references", [])
    references: list[dict[str, Any]] = []
    if isinstance(raw_refs, list):
        for ref in raw_refs[:5]:
            if not isinstance(ref, dict):
                continue
            try:
                page = int(ref.get("page", 0))
            except (TypeError, ValueError):
                page = 0
            if page <= 0:
                continue
            text = str(ref.get("text", "")).strip()
            references.append({"page": page, "text": text})
    return answer, references


def _index_rfx_document(session: WebRuntimeSession, file_path: str, original_name: str) -> None:
    parser = DocumentParser()
    parsed = parser.parse(file_path)
    session.rfx_rag_engine.clear_collection()

    if parsed.pages:
        for page_idx, page_text in enumerate(parsed.pages, start=1):
            session.rfx_rag_engine.add_text_directly(
                page_text,
                source_name=f"rfx_{original_name}_p{page_idx}",
                base_metadata={"page_number": page_idx, "type": "rfx_text"},
            )
        return

    if parsed.text:
        session.rfx_rag_engine.add_text_directly(
            parsed.text,
            source_name=f"rfx_{original_name}",
            base_metadata={"page_number": -1, "type": "rfx_text"},
        )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"ok": "true", "time": _utc_now().isoformat()}


@app.get("/")
def landing() -> FileResponse:
    dist_index = FRONTEND_DIST_DIR / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index)
    raise HTTPException(
        status_code=503,
        detail="Frontend dist가 없습니다. 개발 모드는 http://localhost:3000, 배포 모드는 frontend/kirabot 빌드 후 실행하세요.",
    )


@app.get("/index.html")
def landing_html() -> FileResponse:
    return landing()


@app.get("/auth/google/login")
def auth_google_login() -> RedirectResponse:
    state = _register_oauth_state()
    params = {
        "client_id": _google_client_id(),
        "redirect_uri": _google_redirect_uri(),
        "response_type": "code",
        "scope": _google_scopes(),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    authorize_url = f"{_google_auth_url()}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=authorize_url, status_code=302)


@app.get("/auth/google/callback")
def auth_google_callback(
    code: str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    if error:
        target = f"{_google_post_login_url()}?login_error={urllib.parse.quote_plus(error)}"
        return RedirectResponse(url=target, status_code=302)

    _validate_oauth_state(state)
    if not code:
        raise HTTPException(status_code=400, detail="Google authorization code가 없습니다.")

    token_payload = _exchange_google_code_for_token(code)
    access_token = str(token_payload.get("access_token", "")).strip()
    if not access_token:
        raise HTTPException(status_code=502, detail="Google access_token을 받지 못했습니다.")

    userinfo = _fetch_google_userinfo(access_token)
    external_sub = str(userinfo.get("sub", "")).strip()
    email = str(userinfo.get("email", "")).strip().lower()
    display_name = str(userinfo.get("name", "")).strip()
    if not external_sub:
        raise HTTPException(status_code=502, detail="Google 사용자 식별자(sub)가 없습니다.")

    username = upsert_social_user(
        provider="google",
        external_sub=external_sub,
        email=email,
        display_name=display_name,
    )
    ttl_days = max(1, _safe_int_env("AUTH_SESSION_TTL_DAYS", 7))
    session_token = create_user_session(username=username, ttl_days=ttl_days)

    response = RedirectResponse(url=_google_post_login_url(), status_code=302)
    response.set_cookie(
        key=_auth_cookie_name(),
        value=session_token,
        httponly=True,
        secure=_auth_cookie_secure(),
        samesite="lax",
        path=_auth_cookie_path(),
        domain=_auth_cookie_domain(),
        max_age=ttl_days * 24 * 60 * 60,
    )
    return response


@app.get("/auth/me")
def auth_me(request: Request) -> dict[str, Any]:
    session_token = request.cookies.get(_auth_cookie_name(), "")
    username = resolve_user_from_session(session_token)
    if not username:
        return {"ok": True, "authenticated": False, "user": None}

    profile = get_user_profile(username)
    return {
        "ok": True,
        "authenticated": True,
        "user": {
            "id": username,
            "username": username,
            "name": username,
            "email": profile.get("email", ""),
            "provider": profile.get("provider", ""),
        },
    }


@app.post("/auth/logout")
def auth_logout(request: Request) -> JSONResponse:
    session_token = request.cookies.get(_auth_cookie_name(), "")
    if session_token:
        invalidate_user_session(session_token)

    response = JSONResponse({"ok": True})
    response.delete_cookie(
        key=_auth_cookie_name(),
        path=_auth_cookie_path(),
        domain=_auth_cookie_domain(),
    )
    return response


@app.post("/api/session")
def create_session() -> dict[str, str]:
    session_id = uuid.uuid4().hex[:24]
    _get_or_create_session(session_id)
    return {"session_id": session_id}


@app.post("/api/session/stats")
def session_stats(payload: SessionPayload) -> dict[str, Any]:
    session = _get_or_create_session(payload.session_id)
    stats = session.rag_engine.get_stats()
    return {
        "session_id": session.session_id,
        "company_chunks": stats.get("total_documents", 0),
        "created_at": session.created_at.isoformat(),
        "last_used_at": session.last_used_at.isoformat(),
    }


@app.post("/api/usage/me")
def usage_me(payload: SessionPayload, request: Request) -> dict[str, Any]:
    actor_key, username = _resolve_usage_actor(request, payload.session_id)
    chat_counts = get_actor_usage_counts(actor_key=actor_key, action="chat")
    analyze_counts = get_actor_usage_counts(actor_key=actor_key, action="analyze")
    chat_limits = _usage_limits_for_action("chat")
    analyze_limits = _usage_limits_for_action("analyze")
    return {
        "ok": True,
        "quota_enabled": _quota_enabled(),
        "actor_key": actor_key,
        "username": username,
        "chat": {
            "today_used": chat_counts["today"],
            "month_used": chat_counts["month"],
            "daily_limit": chat_limits[0],
            "monthly_limit": chat_limits[1],
        },
        "analyze": {
            "today_used": analyze_counts["today"],
            "month_used": analyze_counts["month"],
            "daily_limit": analyze_limits[0],
            "monthly_limit": analyze_limits[1],
        },
    }


@app.get("/api/admin/usage")
def admin_usage(request: Request) -> dict[str, Any]:
    token = str(request.cookies.get(_auth_cookie_name(), "") or "")
    username = str(resolve_user_from_session(token) or "")
    if not username or username not in _admin_usernames():
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return {
        "ok": True,
        "username": username,
        "overview": get_usage_overview(),
        "by_actor": list_usage_by_actor(limit=300),
    }


@app.post("/api/company/upload")
async def upload_company_documents(
    session_id: str = Form(...),
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="업로드 파일이 없습니다.")

    session = _get_or_create_session(session_id)
    upload_dir = _session_upload_dir(session.session_id, "company")

    uploaded_names: list[str] = []
    file_urls: list[str] = []
    total_chunks = 0
    for file in files:
        saved_path = await _save_upload_file(file, upload_dir)
        uploaded_names.append(file.filename or saved_path.name)
        file_urls.append(f"/api/files/{session.session_id}/company/{saved_path.name}")
        total_chunks += session.rag_engine.add_document(str(saved_path))

    stats = session.rag_engine.get_stats()
    return {
        "ok": True,
        "uploaded_files": uploaded_names,
        "fileUrls": file_urls,
        "added_chunks": total_chunks,
        "company_chunks": stats.get("total_documents", 0),
    }


@app.post("/api/company/clear")
def clear_company_documents(payload: SessionPayload) -> dict[str, Any]:
    session = _get_or_create_session(payload.session_id)
    session.rag_engine.clear_collection()

    upload_dir = ROOT_DIR / "data" / "web_uploads" / session.session_id / "company"
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)

    return {"ok": True, "company_chunks": 0}


@app.post("/api/analyze/upload")
async def analyze_uploaded_document(
    request: Request,
    session_id: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    session = _get_or_create_session(session_id)
    company_chunk_count = int(session.rag_engine.get_stats().get("total_documents", 0))

    quota = _enforce_quota_or_raise(
        request=request,
        session_id=session.session_id,
        action="analyze",
        metadata={
            "path": "/api/analyze/upload",
            "filename": str(file.filename or ""),
        },
    )

    api_key = _openai_api_key()
    upload_dir = _session_upload_dir(session.session_id, "target")
    saved_path = await _save_upload_file(file, upload_dir)

    analyzer = RFxAnalyzer(
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )

    try:
        analysis = analyzer.analyze(str(saved_path))
        # 회사 문서가 있으면 매칭, 없으면 자격요건 추출만
        if company_chunk_count > 0:
            matcher = QualificationMatcher(
                rag_engine=session.rag_engine,
                api_key=api_key,
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            )
            matching = matcher.match(analysis)
        else:
            matching = None
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"문서 분석 실패: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"문서 분석 중 오류: {exc}") from exc

    _index_rfx_document(session=session, file_path=str(saved_path), original_name=file.filename or "target")
    session.latest_rfx_analysis = analysis
    session.latest_matching_result = matching
    session.latest_document_name = file.filename or saved_path.name

    file_url = f"/api/files/{session.session_id}/target/{saved_path.name}"

    return {
        "ok": True,
        "filename": file.filename,
        "session_id": session.session_id,
        "company_chunks": company_chunk_count,
        "quota": quota,
        "analysis": _serialize_rfx_analysis(analysis),
        "matching": _serialize_matching_result(matching) if matching else None,
        "fileUrl": file_url,
    }


@app.post("/api/analyze/text")
def analyze_text(payload: AnalyzeTextPayload, request: Request) -> dict[str, Any]:
    session = _get_or_create_session(payload.session_id)
    company_chunk_count = int(session.rag_engine.get_stats().get("total_documents", 0))

    quota = _enforce_quota_or_raise(
        request=request,
        session_id=session.session_id,
        action="analyze",
        metadata={"path": "/api/analyze/text", "source": "direct_text"},
    )

    api_key = _openai_api_key()
    analyzer = RFxAnalyzer(
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )

    analysis = analyzer.analyze_text(payload.document_text)
    if company_chunk_count > 0:
        matcher = QualificationMatcher(
            rag_engine=session.rag_engine,
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )
        matching = matcher.match(analysis)
    else:
        matching = None

    session.rfx_rag_engine.clear_collection()
    session.rfx_rag_engine.add_text_directly(
        payload.document_text,
        source_name="rfx_direct_input",
        base_metadata={"page_number": -1, "type": "rfx_text"},
    )
    session.latest_rfx_analysis = analysis
    session.latest_matching_result = matching
    session.latest_document_name = "direct_input.txt"

    return {
        "ok": True,
        "session_id": session.session_id,
        "company_chunks": company_chunk_count,
        "quota": quota,
        "analysis": _serialize_rfx_analysis(analysis),
        "matching": _serialize_matching_result(matching) if matching else None,
    }


class RematchPayload(BaseModel):
    session_id: str


@app.post("/api/rematch")
def rematch_with_company_docs(payload: RematchPayload, request: Request) -> dict[str, Any]:
    """회사 문서 등록 후 기존 분석 결과에 대해 매칭만 재실행."""
    session = _get_or_create_session(payload.session_id)
    if session.latest_rfx_analysis is None:
        raise HTTPException(status_code=400, detail="재매칭할 분석 결과가 없습니다.")

    company_chunk_count = int(session.rag_engine.get_stats().get("total_documents", 0))
    if company_chunk_count <= 0:
        raise HTTPException(status_code=400, detail="등록된 회사 문서가 없습니다.")

    api_key = _openai_api_key()
    matcher = QualificationMatcher(
        rag_engine=session.rag_engine,
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )
    matching = matcher.match(session.latest_rfx_analysis)
    session.latest_matching_result = matching

    return {
        "ok": True,
        "session_id": session.session_id,
        "company_chunks": company_chunk_count,
        "analysis": _serialize_rfx_analysis(session.latest_rfx_analysis),
        "matching": _serialize_matching_result(matching) if matching else None,
        "filename": session.latest_document_name,
    }


@app.post("/api/chat")
def chat_with_references(payload: ChatPayload, request: Request) -> dict[str, Any]:
    session = _get_or_create_session(payload.session_id)
    message = str(payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message가 비어 있습니다.")

    quota = _enforce_quota_or_raise(
        request=request,
        session_id=session.session_id,
        action="chat",
        metadata={"path": "/api/chat"},
    )

    router_model = os.getenv("CHAT_ROUTER_MODEL", os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"))
    confidence_threshold = _safe_float_env("CHAT_ROUTER_CONFIDENCE_THRESHOLD", 0.65)
    min_relevance_score = _safe_float_env("CHAT_MIN_RELEVANCE_SCORE", 0.0)
    enforce_relevance = _safe_bool_env("CHAT_RELEVANCE_ENFORCE", False)
    offtopic_strict = _safe_bool_env("CHAT_OFFTOPIC_STRICT", True)

    decision = route_user_query(
        message=message,
        api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        model=router_model,
        confidence_threshold=confidence_threshold,
        offtopic_strict=offtopic_strict,
    )
    suggested_questions = _build_suggested_questions(
        session=session,
        decision_questions=decision.suggested_questions,
        blocked_offtopic=False,
    )

    company_scores, rfx_scores = _collect_rag_scores(session, message)
    relevance_score = _max_relevance_score(company_scores, rfx_scores)
    has_context = bool(
        (session.rag_engine.collection.count() > 0)
        or (session.rfx_rag_engine.collection.count() > 0)
    )
    min_score = min_relevance_score if enforce_relevance else 0.0
    decision = apply_context_policy(
        decision=decision,
        has_context=has_context,
        relevance_score=relevance_score,
        min_relevance_score=min_score,
    )

    write_router_telemetry(
        log_path=default_router_log_path(),
        message=message,
        decision=decision,
        company_scores=company_scores,
        rfx_scores=rfx_scores,
        relevance_score=relevance_score,
        min_relevance_score=min_score,
        has_context=has_context,
    )

    if decision.policy != ChatPolicy.ALLOW:
        if decision.policy == ChatPolicy.BLOCK_OFFTOPIC:
            suggested_questions = _build_suggested_questions(
                session=session,
                decision_questions=decision.suggested_questions,
                blocked_offtopic=True,
            )
        return {
            "ok": True,
            "blocked": True,
            "policy": decision.policy.value,
            "intent": decision.intent.value,
            "reason": decision.reason,
            "answer": build_policy_response(decision),
            "references": [],
            "suggested_questions": suggested_questions,
            "quota": quota,
        }

    deterministic_gap = _build_gap_answer_from_latest_matching(session=session, message=message)
    if deterministic_gap is not None:
        answer, references = deterministic_gap
        return {
            "ok": True,
            "blocked": False,
            "policy": decision.policy.value,
            "intent": decision.intent.value,
            "reason": f"{decision.reason} | latest_matching_guard",
            "answer": answer,
            "references": references,
            "suggested_questions": suggested_questions,
            "quota": quota,
        }

    api_key = _openai_api_key()
    company_context_text, rfx_context_text, fallback_refs = _build_chat_context(session, message)

    answer, references = _generate_chat_answer(
        api_key=api_key,
        message=message,
        company_context_text=company_context_text,
        rfx_context_text=rfx_context_text,
        session=session,
    )

    references = [ref for ref in references if _is_grounded_in_rfx(ref, rfx_context_text)]
    if not references and fallback_refs:
        references = fallback_refs[:3]

    return {
        "ok": True,
        "blocked": False,
        "policy": decision.policy.value,
        "intent": decision.intent.value,
        "reason": decision.reason,
        "answer": answer,
        "references": references,
        "suggested_questions": suggested_questions,
        "quota": quota,
    }


# ── Phase 1: 공고 검색 (나라장터 Open API) ──


@app.post("/api/bids/search")
async def api_bids_search(payload: BidSearchPayload) -> dict[str, Any]:
    """나라장터 공고 검색."""
    kw = payload.keywords
    if isinstance(kw, list):
        keywords_str = " ".join(kw)
    else:
        keywords_str = str(kw or "").strip()

    try:
        result = await nara_search_bids(
            keywords=keywords_str,
            category=payload.category,
            region=payload.region,
            min_amt=payload.minAmt,
            max_amt=payload.maxAmt,
            period=payload.period,
            exclude_expired=payload.excludeExpired,
            page=payload.page,
            page_size=payload.pageSize,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"나라장터 API 호출 실패: {exc}") from exc
    return result


@app.get("/api/bids/{bid_ntce_no}/attachments")
async def api_bid_attachments(bid_ntce_no: str, bid_ntce_ord: str = "00") -> dict[str, Any]:
    """공고 첨부파일 목록 조회."""
    try:
        attachments = await nara_get_bid_attachments(bid_ntce_no, bid_ntce_ord)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"첨부파일 조회 실패: {exc}") from exc
    return {"attachments": attachments}


# ── Phase 2: 파일 서빙 (문서 미리보기) ──


@app.get("/api/files/{session_id}/{bucket}/{filename}")
def serve_uploaded_file(session_id: str, bucket: str, filename: str) -> FileResponse:
    """업로드된 파일 서빙 (PDF 미리보기 등)."""
    session_id = _sanitize_session_id(session_id)
    if bucket not in ("company", "target"):
        raise HTTPException(status_code=400, detail="유효하지 않은 버킷입니다.")

    # Path traversal 방어
    safe_filename = Path(filename).name
    if not safe_filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="유효하지 않은 파일명입니다.")

    file_path = ROOT_DIR / "data" / "web_uploads" / session_id / bucket / safe_filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    # 파일 경로가 upload 디렉토리 내에 있는지 재검증
    try:
        file_path.resolve().relative_to((ROOT_DIR / "data" / "web_uploads").resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="접근이 허용되지 않은 경로입니다.")

    from urllib.parse import quote
    encoded_name = quote(safe_filename)
    return FileResponse(
        path=str(file_path),
        filename=safe_filename,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}"},
    )


# ── Phase 3: 공고 첨부파일 자동분석 ──


@app.post("/api/bids/analyze")
async def analyze_bid_from_nara(payload: BidAnalyzePayload, request: Request) -> dict[str, Any]:
    """나라장터 공고 첨부파일 자동 다운로드 + 분석."""
    session = _get_or_create_session(payload.session_id)
    company_chunk_count = int(session.rag_engine.get_stats().get("total_documents", 0))

    quota = _enforce_quota_or_raise(
        request=request,
        session_id=session.session_id,
        action="analyze",
        metadata={"path": "/api/bids/analyze", "bid_ntce_no": payload.bid_ntce_no},
    )

    # 1. 첨부파일 3단계 폴백: 상세 API → e발주 API → 수동 업로드
    attachments: list[dict[str, Any]] = []
    attachment_error: str | None = None

    # Tier 1: 상세 API (ntceSpecFileNm1~10 — 공고서 원본/변환본)
    try:
        attachments = await nara_get_bid_detail_attachments(
            payload.bid_ntce_no, payload.bid_ntce_ord, payload.category,
        )
    except Exception as exc:
        logger.info("상세 API 폴백 (bid=%s): %s", payload.bid_ntce_no, exc)

    # Tier 2: e발주 API (제안요청서, 기타문서)
    if not attachments:
        try:
            attachments = await nara_get_bid_attachments(payload.bid_ntce_no, payload.bid_ntce_ord)
        except ValueError as exc:
            attachment_error = str(exc)
        except Exception as exc:
            attachment_error = f"첨부파일 조회 실패: {exc}"
            logger.warning("첨부파일 API 오류 (bid=%s): %s", payload.bid_ntce_no, exc)

    # Tier 3: 수동 업로드 폴백
    if not attachments:
        raise HTTPException(
            status_code=422,
            detail=json.dumps({
                "code": "attachment_unavailable",
                "message": "공고 첨부파일을 자동으로 가져올 수 없습니다. 나라장터에서 직접 다운로드 후 업로드해주세요.",
                "reason": attachment_error or "첨부파일 정보 없음",
                "bidNtceNo": payload.bid_ntce_no,
                "bidNtceOrd": payload.bid_ntce_ord,
            }, ensure_ascii=False),
        )

    # 2. 최적 첨부파일 선택
    best = pick_best_attachment(attachments)
    if not best:
        raise HTTPException(status_code=404, detail="분석 가능한 첨부파일이 없습니다.")

    # 3. 다운로드
    target_dir = _session_upload_dir(session.session_id, "target")
    try:
        local_path = await nara_download_attachment(best["fileUrl"], str(target_dir), fallback_name=best["fileNm"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"첨부파일 다운로드 실패: {exc}") from exc

    # 4. 분석
    api_key = _openai_api_key()
    analyzer = RFxAnalyzer(
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )
    matcher = QualificationMatcher(
        rag_engine=session.rag_engine,
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )

    analysis = analyzer.analyze(local_path)

    # 회사 문서가 있으면 매칭 수행, 없으면 스킵
    matching = None
    if company_chunk_count > 0:
        matching = matcher.match(analysis)

    _index_rfx_document(session=session, file_path=local_path, original_name=best["fileNm"])
    session.latest_rfx_analysis = analysis
    session.latest_matching_result = matching
    session.latest_document_name = best["fileNm"]

    # 5. fileUrl 생성
    local_filename = Path(local_path).name
    file_url = f"/api/files/{session.session_id}/target/{local_filename}"

    return {
        "ok": True,
        "filename": best["fileNm"],
        "session_id": session.session_id,
        "company_chunks": company_chunk_count,
        "quota": quota,
        "analysis": _serialize_rfx_analysis(analysis),
        "matching": _serialize_matching_result(matching) if matching else None,
        "fileUrl": file_url,
    }


# ── 일괄 평가 (레거시) ──


@app.post("/api/bids/evaluate-batch")
async def api_bids_evaluate_batch(payload: BidEvaluateBatchPayload, request: Request) -> dict[str, Any]:
    """선택된 공고들을 순차 다운로드 + 분석하여 일괄 평가."""
    session = _get_or_create_session(payload.session_id)
    company_chunk_count = int(session.rag_engine.get_stats().get("total_documents", 0))

    api_key = _openai_api_key()
    jobs: list[dict[str, Any]] = []

    for bid_ntce_no in payload.bid_ntce_nos:
        job: dict[str, Any] = {
            "id": bid_ntce_no,
            "bidNoticeId": bid_ntce_no,
            "isEligible": None,
            "evaluationReason": "",
            "actionPlan": None,
            "bidNotice": {"id": bid_ntce_no, "title": bid_ntce_no, "region": None, "deadlineAt": None, "url": None},
        }

        try:
            # 1. 첨부파일 3단계 폴백: 상세 API → e발주 API
            attachments = await nara_get_bid_detail_attachments(bid_ntce_no, "00")
            if not attachments:
                attachments = await nara_get_bid_attachments(bid_ntce_no, "00")
            best = pick_best_attachment(attachments) if attachments else None
            if not best:
                job["evaluationReason"] = "첨부파일이 없어 분석 불가"
                jobs.append(job)
                continue

            target_dir = _session_upload_dir(session.session_id, "target")
            local_path = await nara_download_attachment(best["fileUrl"], str(target_dir), fallback_name=best["fileNm"])

            # 2. 분석
            analyzer = RFxAnalyzer(api_key=api_key, model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

            analysis = analyzer.analyze(local_path)

            matching = None
            if company_chunk_count > 0:
                matcher = QualificationMatcher(
                    rag_engine=session.rag_engine,
                    api_key=api_key,
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                )
                matching = matcher.match(analysis)

            job["bidNotice"]["title"] = analysis.title or bid_ntce_no
            job["isEligible"] = matching.overall_status != MatchStatus.FAIL if matching else None
            job["evaluationReason"] = matching.summary if matching else "자격요건 추출 완료 (회사 문서 미등록으로 매칭 미수행)"
            if matching and matching.preparation_guide:
                job["actionPlan"] = matching.preparation_guide

        except Exception as exc:
            job["evaluationReason"] = f"분석 실패: {exc}"

        jobs.append(job)

    return {
        "jobsCreated": len(jobs),
        "jobs": jobs,
    }


# ── 제안서 초안 생성 ──


class ProposalGeneratePayload(BaseModel):
    session_id: str
    bid_notice_id: str


class GeneralChatPayload(BaseModel):
    message: str
    history: list[dict[str, str]] = []


@app.post("/api/chat/general")
async def general_chat(payload: GeneralChatPayload) -> dict[str, Any]:
    """세션/문서 없이 일반 대화. 공공조달 도우미 역할."""
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message가 비어 있습니다.")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"answer": "죄송합니다, AI 응답 기능이 현재 비활성화되어 있어요. 좌측 메뉴에서 기능을 선택해주세요."}

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    system_msg = (
        "당신은 KiraBot, 공공조달·입찰 전문 AI 비서입니다. "
        "사용자의 질문에 친절하고 간결하게 답변하세요. "
        "공고 검색, 문서 분석, 입찰 전략 등에 대해 도움을 줄 수 있습니다. "
        "사용자가 공고를 검색하고 싶어하면 좌측 '공고 검색/분석' 메뉴를 안내하세요. "
        "한국어로 답변하세요. 답변은 3~4문장 이내로 간결하게."
    )

    messages = [{"role": "system", "content": system_msg}]
    for h in payload.history[-6:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": message})

    try:
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        answer = resp.choices[0].message.content or "응답을 생성하지 못했어요."
    except Exception as e:
        answer = f"AI 응답 생성 중 오류가 발생했어요: {str(e)}"

    return {"answer": answer}


@app.post("/api/proposal/generate")
async def generate_proposal(payload: ProposalGeneratePayload) -> dict[str, Any]:
    """분석된 문서 기반 제안서 초안 생성."""
    session = _get_or_create_session(payload.session_id)

    if session.latest_rfx_analysis is None:
        raise HTTPException(status_code=400, detail="분석된 문서가 없습니다. 먼저 문서를 분석해주세요.")

    # Build analysis text from session's stored RFx analysis
    analysis = session.latest_rfx_analysis
    analysis_text = f"공고명: {analysis.title}\n"
    analysis_text += f"발주기관: {analysis.issuing_org}\n"
    analysis_text += f"문서유형: {analysis.document_type}\n"
    if analysis.budget:
        analysis_text += f"예산: {analysis.budget}\n"
    if analysis.project_period:
        analysis_text += f"사업기간: {analysis.project_period}\n"
    if analysis.requirements:
        analysis_text += "\n자격요건:\n"
        for req in analysis.requirements:
            analysis_text += f"- [{req.category}] {req.description}\n"
    if analysis.evaluation_criteria:
        analysis_text += "\n평가기준:\n"
        for crit in analysis.evaluation_criteria:
            analysis_text += f"- [{crit.category}] {crit.item} ({crit.score}점)\n"

    # Build company summary from RAG engine
    company_text = ""
    try:
        if session.rag_engine.collection.count() > 0:
            company_results = session.rag_engine.search("회사 소개 강점 실적 인증", top_k=5)
            company_text = "\n".join(r.text for r in company_results if r.text)
    except Exception:
        pass

    # Try calling rag_engine if available
    rag_url = os.environ.get("FASTAPI_URL", "http://localhost:8001")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{rag_url}/api/generate-proposal", json={
                "bid_text": analysis_text,
                "company_text": company_text,
            })
            if resp.status_code == 200:
                data = resp.json()
                return {"sections": data.get("sections", {})}
    except Exception:
        pass

    # Fallback: generate template sections using OpenAI
    try:
        api_key = _openai_api_key()
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        system_prompt = """당신은 공공조달 입찰 제안서 작성 전문가입니다.
주어진 공고 분석 결과와 회사 정보를 바탕으로 제안서 초안의 각 섹션을 작성하세요.
반드시 JSON 객체로 응답하세요. 키는 섹션 제목, 값은 섹션 내용입니다.

필수 섹션: "사업 이해 및 목표", "수행 방법론", "추진 일정", "투입 인력 구성", "기대 효과"
각 섹션은 300-500자로 작성하세요. 한국어로 작성하세요."""

        user_prompt = f"""[공고 분석 결과]
{analysis_text}

[회사 정보]
{company_text or '회사 정보 없음'}

위 정보를 바탕으로 제안서 초안을 JSON 형식으로 작성해주세요."""

        response = client.chat.completions.create(
            model=model,
            max_tokens=3000,
            temperature=0.5,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = (response.choices[0].message.content or "{}").strip()
        sections = json.loads(content)
        if isinstance(sections, dict) and sections:
            return {"sections": sections}
    except Exception as exc:
        logger.warning("OpenAI 제안서 생성 실패: %s", exc)

    # Final fallback: basic template
    title = analysis.title or payload.bid_notice_id
    sections = {
        "사업 이해 및 목표": f"본 제안서는 '{title}' 공고에 대한 제안입니다.\n발주기관의 사업 목적과 요구사항을 분석하여 최적의 수행 방안을 제시합니다.",
        "수행 방법론": "사업 수행을 위한 체계적인 방법론을 적용합니다.\n요구사항 분석, 설계, 구현, 테스트, 안정화의 단계별 접근법을 따릅니다.",
        "추진 일정": "사업 착수 후 체계적인 일정 관리를 통해 기한 내 완료를 목표로 합니다.\n주요 마일스톤을 설정하고 단계별 산출물을 제출합니다.",
        "투입 인력 구성": "프로젝트 관리자(PM)를 중심으로 분야별 전문 인력을 투입합니다.\n각 인력의 역할과 책임을 명확히 정의합니다.",
        "기대 효과": "본 사업의 성공적 수행을 통해 발주기관의 업무 효율성 향상과 서비스 품질 개선이 기대됩니다.",
    }
    return {"sections": sections}


# ── 알림 설정 CRUD ──

ALERT_SETTINGS_DIR = ROOT_DIR / "data" / "alert_settings"


@app.post("/api/alerts/settings")
async def save_alert_settings(payload: dict) -> dict[str, Any]:
    """공고 알림 설정 저장."""
    session_id = payload.get("session_id", "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id가 필요합니다.")

    settings = {
        "keywords": payload.get("keywords", []),
        "categories": payload.get("categories", []),
        "regions": payload.get("regions", []),
        "minAmt": payload.get("minAmt"),
        "maxAmt": payload.get("maxAmt"),
        "email": payload.get("email", "").strip(),
        "schedule": payload.get("schedule", "daily"),
    }

    if not settings["email"]:
        raise HTTPException(status_code=400, detail="이메일 주소가 필요합니다.")

    ALERT_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings_path = ALERT_SETTINGS_DIR / f"{session_id}.json"
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True}


@app.get("/api/alerts/settings")
async def get_alert_settings(session_id: str = "") -> dict[str, Any]:
    """공고 알림 설정 조회."""
    session_id = session_id.strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id가 필요합니다.")

    settings_path = ALERT_SETTINGS_DIR / f"{session_id}.json"
    if not settings_path.exists():
        return {"settings": None}

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        return {"settings": data}
    except Exception:
        return {"settings": None}


@app.delete("/api/alerts/settings")
async def delete_alert_settings(session_id: str = "") -> dict[str, Any]:
    """공고 알림 설정 삭제."""
    session_id = session_id.strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id가 필요합니다.")

    settings_path = ALERT_SETTINGS_DIR / f"{session_id}.json"
    if settings_path.exists():
        settings_path.unlink()

    return {"ok": True}


# ── Dashboard Summary + Smart Fit Score ──


@app.get("/api/dashboard/summary")
def dashboard_summary(session_id: str = "") -> dict[str, Any]:
    """대시보드 요약 데이터 반환.

    세션에 저장된 분석 결과를 기반으로 totalAnalyzed, goCount 등을 집계한다.
    아직 구현되지 않은 항목(newMatches, deadlineSoon 등)은 0/빈값으로 반환.
    """
    session_id = session_id.strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id가 필요합니다.")

    total_analyzed = 0
    go_count = 0
    recent_searches: list[dict[str, Any]] = []
    smart_fit_top5: list[dict[str, Any]] = []

    normalized = _sanitize_session_id(session_id)
    session = SESSIONS.get(normalized)
    if session is not None:
        # 현재 세션에 분석 결과가 있으면 카운트
        if session.latest_rfx_analysis is not None:
            total_analyzed = 1
        if session.latest_matching_result is not None:
            rec = (session.latest_matching_result.recommendation or "").upper()
            if rec == "GO":
                go_count = 1

    return {
        "newMatches": 0,
        "deadlineSoon": 0,
        "goCount": go_count,
        "totalAnalyzed": total_analyzed,
        "recentSearches": recent_searches,
        "smartFitTop5": smart_fit_top5,
    }


def _compute_keyword_score(keywords: list[str], bid_title: str, max_score: int = 20) -> tuple[int, str]:
    """키워드 중복 기반 점수를 계산한다.

    각 키워드가 bid_title 에 포함되면 가점. 최대 max_score.
    """
    if not keywords or not bid_title:
        return 0, ""

    title_lower = bid_title.lower()
    matched: list[str] = []
    for kw in keywords:
        kw_norm = kw.strip().lower()
        if kw_norm and kw_norm in title_lower:
            matched.append(kw.strip())

    if not matched:
        return 0, "키워드 일치 없음"

    ratio = len(matched) / len(keywords)
    score = min(max_score, round(ratio * max_score))
    detail = f"일치 키워드: {', '.join(matched)} ({len(matched)}/{len(keywords)})"
    return score, detail


@app.post("/api/smart-fit/score")
def smart_fit_score(payload: SmartFitScorePayload) -> dict[str, Any]:
    """Smart Fit 점수 계산.

    - qualification (max 60): 회사문서 + 분석결과 기반 overall_score 반영
    - keywords (max 20): 키워드-공고제목 중복률
    - region (max 10): placeholder (항상 10)
    - experience (max 10): placeholder (항상 5)
    """
    session_id = payload.session_id.strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id가 필요합니다.")

    normalized = _sanitize_session_id(session_id)
    session = SESSIONS.get(normalized)

    # --- qualification (max 60) ---
    qual_score = 0
    qual_detail = "세션 없음"
    if session is not None:
        company_count = int(session.rag_engine.get_stats().get("total_documents", 0))
        if company_count <= 0:
            qual_score = 0
            qual_detail = "회사 문서 미등록"
        elif session.latest_matching_result is not None:
            # overall_score is 0-100, scale to 0-60
            raw = session.latest_matching_result.overall_score
            qual_score = min(60, max(0, round(raw * 60 / 100)))
            qual_detail = (
                f"종합 적합도 {raw:.0f}% "
                f"(충족 {session.latest_matching_result.met_count}, "
                f"부분충족 {session.latest_matching_result.partially_met_count}, "
                f"미충족 {session.latest_matching_result.not_met_count})"
            )
        else:
            qual_score = 0
            qual_detail = "분석 결과 없음 (공고 문서를 분석해주세요)"

    # --- keywords (max 20) ---
    # bid_title: from payload or from session's latest analysis
    bid_title = payload.bid_title.strip()
    if not bid_title and session is not None and session.latest_rfx_analysis is not None:
        bid_title = session.latest_rfx_analysis.title or ""

    kw_score, kw_detail = _compute_keyword_score(payload.keywords, bid_title, max_score=20)

    # --- region (max 10) — placeholder ---
    region_score = 10
    region_detail = "지역 필터 미적용 (기본값)"

    # --- experience (max 10) — placeholder ---
    exp_score = 5
    exp_detail = "경험 평가 미구현 (기본값)"

    total = qual_score + kw_score + region_score + exp_score

    return {
        "totalScore": total,
        "breakdown": {
            "qualification": {"score": qual_score, "maxScore": 60, "details": qual_detail},
            "keywords": {"score": kw_score, "maxScore": 20, "details": kw_detail},
            "region": {"score": region_score, "maxScore": 10, "details": region_detail},
            "experience": {"score": exp_score, "maxScore": 10, "details": exp_detail},
        },
    }


# ── 발주예측 (Forecast) ──


@app.get("/api/forecast/popular")
async def get_popular_agencies() -> dict[str, Any]:
    """인기 발주기관 목록 반환."""
    agencies = [
        "한국도로공사", "한국수자원공사", "한국전력공사", "한국철도공사",
        "한국토지주택공사", "국방부", "행정안전부", "과학기술정보통신부",
        "교육부", "보건복지부", "환경부", "국토교통부",
        "산업통상자원부", "조달청", "방위사업청", "경찰청",
        "소방청", "기상청", "특허청", "관세청",
    ]
    return {"agencies": agencies}


@app.get("/api/forecast/{org_name}")
async def get_org_forecast(org_name: str) -> dict[str, Any]:
    """기관별 입찰 공고 패턴 데이터 반환."""
    try:
        results_3m = await nara_search_bids(
            keywords=org_name,
            category="all",
            period="3m",
            exclude_expired=False,
            page=1,
            page_size=100,
        )

        # 월별 집계
        monthly: dict[str, dict[str, Any]] = {}
        for bid in results_3m.get("notices", []):
            deadline = bid.get("deadlineAt") or ""
            if deadline:
                month_key = deadline[:7]  # "2026-02"
                if month_key not in monthly:
                    monthly[month_key] = {"count": 0, "totalAmt": 0}
                monthly[month_key]["count"] += 1

        return {
            "orgName": org_name,
            "monthlyPattern": monthly,
            "recentBids": results_3m.get("notices", [])[:10],
            "aiInsight": (
                f"{org_name}의 최근 3개월 입찰 공고 패턴입니다. "
                "이 데이터는 참고용이며 실제 발주 계획과 다를 수 있습니다."
            ),
            "total": results_3m.get("total", 0),
        }
    except Exception as exc:
        logger.warning("발주예측 조회 실패 (org=%s): %s", org_name, exc)
        return {
            "orgName": org_name,
            "monthlyPattern": {},
            "recentBids": [],
            "aiInsight": "데이터를 불러오는 중 오류가 발생했습니다.",
            "total": 0,
        }


@app.get("/{path_name:path}")
def frontend_spa(path_name: str) -> FileResponse:
    """
    React SPA fallback.
    - dist 내 정적 파일이 있으면 해당 파일 반환
    - 없으면 index.html 반환
    """
    dist_index = FRONTEND_DIST_DIR / "index.html"
    if not dist_index.exists():
        raise HTTPException(status_code=404, detail="Frontend build output(dist)가 없습니다.")

    requested = (FRONTEND_DIST_DIR / path_name).resolve()
    if str(requested).startswith(str(FRONTEND_DIST_DIR.resolve())) and requested.is_file():
        return FileResponse(requested)
    return FileResponse(dist_index)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("WEB_API_HOST", "0.0.0.0").strip() or "0.0.0.0"
    try:
        port = int(os.getenv("WEB_API_PORT", "8010").strip())
    except ValueError:
        port = 8010

    uvicorn.run("main:app", host=host, port=port, reload=False)
