"""
Kira Web Runtime API

Streamlit UI 없이 웹 랜딩(index.html)에서 Kira 분석 엔진을 직접 실행하기 위한 API 서버.
"""

from __future__ import annotations

import json
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

load_dotenv(ROOT_DIR / ".env")

from engine import RAGEngine  # noqa: E402
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


ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
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
    total_chunks = 0
    for file in files:
        saved_path = await _save_upload_file(file, upload_dir)
        uploaded_names.append(file.filename or saved_path.name)
        total_chunks += session.rag_engine.add_document(str(saved_path))

    stats = session.rag_engine.get_stats()
    return {
        "ok": True,
        "uploaded_files": uploaded_names,
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
    if company_chunk_count <= 0:
        raise HTTPException(status_code=400, detail="회사 문서를 먼저 업로드해주세요.")

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
    matcher = QualificationMatcher(
        rag_engine=session.rag_engine,
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )

    analysis = analyzer.analyze(str(saved_path))
    matching = matcher.match(analysis)
    _index_rfx_document(session=session, file_path=str(saved_path), original_name=file.filename or "target")
    session.latest_rfx_analysis = analysis
    session.latest_matching_result = matching
    session.latest_document_name = file.filename or saved_path.name

    return {
        "ok": True,
        "filename": file.filename,
        "session_id": session.session_id,
        "company_chunks": company_chunk_count,
        "quota": quota,
        "analysis": _serialize_rfx_analysis(analysis),
        "matching": _serialize_matching_result(matching),
    }


@app.post("/api/analyze/text")
def analyze_text(payload: AnalyzeTextPayload, request: Request) -> dict[str, Any]:
    session = _get_or_create_session(payload.session_id)
    company_chunk_count = int(session.rag_engine.get_stats().get("total_documents", 0))
    if company_chunk_count <= 0:
        raise HTTPException(status_code=400, detail="회사 문서를 먼저 업로드해주세요.")

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
    matcher = QualificationMatcher(
        rag_engine=session.rag_engine,
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )

    analysis = analyzer.analyze_text(payload.document_text)
    matching = matcher.match(analysis)
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
        "matching": _serialize_matching_result(matching),
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
