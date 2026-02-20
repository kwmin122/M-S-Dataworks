"""
RFx AI 입찰 분석 어시스턴트 - Streamlit MVP (v2: PDF 뷰어 + 하이라이트)

🔑 핵심 변경사항:
   - ChatPDF / Adobe Acrobat AI 스타일 split 레이아웃
   - 왼쪽: 챗봇 대화, 오른쪽: PDF 뷰어 (하이라이트 포함)
   - AI 답변 시 참조 페이지로 자동 이동 + 노란색 형광펜 하이라이트

📌 설계 근거 (리서치 기반):
   1. ChatPDF: side-by-side 인터페이스, 클릭 가능 인용, 원문 즉시 확인
   2. Adobe Acrobat AI: 번호 매긴 참조 → 클릭 시 원문 하이라이트
   3. LightPDF: 각주/참조 → 원문 네비게이션, 마크다운 테이블 답변
   4. Monica ChatPDF: 원문 참조 지원, 사이드바이사이드 비교

   → 공통 패턴: "Chat + PDF Viewer + Clickable Citations + Auto-scroll"
     이것이 AI PDF 도구의 업계 표준 UX.

📌 기술 선택 이유:
   - streamlit-pdf-viewer: PDF.js 기반, 어노테이션 오버레이, scroll_to_page/annotation 지원
   - PyMuPDF(fitz): search_for()로 정확한 텍스트 좌표 획득, 한국어 지원
   - Streamlit columns: 반응형 split 레이아웃, 세션 상태로 동적 업데이트

실행: streamlit run app.py
필수: pip install streamlit streamlit-pdf-viewer pymupdf openai chromadb
"""

import os
import sys
import json
import csv
import io
import tempfile
import uuid
import importlib.util
from datetime import datetime, timedelta, timezone
from collections import Counter
from typing import Any
import streamlit as st
from dotenv import load_dotenv

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

# PDF 하이라이트 모듈
from pdf_highlighter import PDFHighlighter, HighlightManager
from chat_router import (
    RouteIntent,
    ChatPolicy,
    RouteDecision,
    route_user_query,
    apply_context_policy,
    build_policy_response,
    write_router_telemetry,
    default_router_log_path,
)
from ui_tokens import build_streamlit_css
from user_store import (
    init_user_store,
    touch_last_login,
    resolve_user_from_session,
    invalidate_user_session,
    save_company_file,
    list_company_files,
    count_company_files,
    delete_company_files,
    username_to_scope,
    get_admin_overview,
    get_usage_overview,
    list_user_activity,
    list_recent_company_files,
    list_usage_by_actor,
)


# ============================================================
# STEP 1: 페이지 설정
# ============================================================

st.set_page_config(
    page_title="M&S Kira 문서 분석 어시스턴트",
    page_icon="🤖",
    layout="wide",             # wide 필수: split 레이아웃
    initial_sidebar_state="collapsed"  # 사이드바 접어서 화면 최대화
)

# ── 커스텀 CSS ──
st.markdown(build_streamlit_css(), unsafe_allow_html=True)


# ============================================================
# STEP 2: 세션 상태 초기화
# ============================================================

init_user_store()


def _auth_cookie_name() -> str:
    return os.getenv("AUTH_COOKIE_NAME", "kira_auth").strip() or "kira_auth"


def _auth_cookie_secure() -> bool:
    raw = os.getenv("AUTH_COOKIE_SECURE", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _social_login_url(provider: str) -> str:
    provider_key = provider.strip().lower()
    if provider_key == "google":
        return os.getenv("SOCIAL_LOGIN_GOOGLE_URL", "").strip()
    if provider_key == "kakao":
        return os.getenv("SOCIAL_LOGIN_KAKAO_URL", "").strip()
    return ""


def _social_logout_url() -> str:
    return os.getenv("SOCIAL_AUTH_LOGOUT_URL", "/auth/logout").strip() or "/auth/logout"


def init_session_state():
    """Streamlit 세션 상태 초기화"""
    env_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    defaults = {
        # 기존
        "api_key": env_api_key,
        "rag_engine": None,  # 레거시 호환용 (company_rag_engine alias)
        "company_rag_engine": None,
        "rfx_rag_engine": None,
        "chat_engine": None,
        "rfx_analysis": None,
        "matching_result": None,
        "chat_history": [],
        "company_docs_loaded": False,
        "rfx_loaded": False,
        "session_id": "",
        "validated_api_key": "",
        "is_authenticated": False,
        "auth_username": "",
        "auth_session_token": "",
        "auth_restore_checked": False,
        "auth_initialized_user": "",
        "saved_company_files": [],
        "delete_confirm_armed_at": "",
        "delete_last_executed_at": "",
        "last_route_intent": RouteIntent.UNKNOWN.value,
        "last_route_confidence": 0.0,
        "last_route_policy": ChatPolicy.ASK_CLARIFY.value,
        "last_route_reason": "",
        "last_relevance_score": 0.0,
        "last_context_available": False,
        "analysis_opinion_mode": "balanced",
        "analysis_last_logged_mode": "",
        "pdf_viewer_available": False,
        "pdf_viewer_required": True,
        "pdf_viewer_error": "",

        # 🆕 PDF 뷰어 + 하이라이트 관련
        "pdf_bytes": None,              # 업로드된 PDF 바이너리
        "pdf_filename": "",             # PDF 파일명
        "highlight_manager": None,      # HighlightManager 인스턴스
        "current_annotations": [],      # 현재 어노테이션 리스트
        "scroll_to_page": None,         # 자동 스크롤 대상 페이지
        "scroll_to_annotation": None,   # 자동 스크롤 대상 어노테이션
        "current_references": [],       # 현재 답변의 참조 정보
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # 브라우저 세션 단위 격리 ID
    if not st.session_state.session_id:
        st.session_state.session_id = uuid.uuid4().hex[:12]

init_session_state()


def _reset_user_runtime_state() -> None:
    """로그인 사용자 변경/로그아웃 시 런타임 상태 초기화"""
    st.session_state.rag_engine = None
    st.session_state.company_rag_engine = None
    st.session_state.rfx_rag_engine = None
    st.session_state.rfx_analysis = None
    st.session_state.matching_result = None
    st.session_state.chat_history = []
    st.session_state.company_docs_loaded = False
    st.session_state.rfx_loaded = False
    st.session_state.saved_company_files = []
    st.session_state.current_annotations = []
    st.session_state.current_references = []
    st.session_state.scroll_to_page = None
    st.session_state.scroll_to_annotation = None
    st.session_state.last_route_intent = RouteIntent.UNKNOWN.value
    st.session_state.last_route_confidence = 0.0
    st.session_state.last_route_policy = ChatPolicy.ASK_CLARIFY.value
    st.session_state.last_route_reason = ""
    st.session_state.last_relevance_score = 0.0
    st.session_state.last_context_available = False
    st.session_state.analysis_opinion_mode = "balanced"
    st.session_state.pdf_bytes = None
    st.session_state.pdf_filename = ""
    st.session_state.highlight_manager = None
    st.session_state.delete_confirm_armed_at = ""
    st.session_state.delete_last_executed_at = ""


def _restore_auth_from_cookie() -> None:
    """
    HttpOnly 인증 쿠키 기반 로그인 상태 복원.
    URL 파라미터 토큰은 보안상 지원하지 않는다.
    """
    if st.session_state.auth_restore_checked:
        return
    st.session_state.auth_restore_checked = True

    token = ""
    try:
        token = str(st.context.cookies.get(_auth_cookie_name()) or "")
    except Exception:
        token = ""

    if not token:
        return
    username = resolve_user_from_session(token)
    if not username:
        return
    st.session_state.is_authenticated = True
    st.session_state.auth_username = username
    st.session_state.auth_session_token = token
    touch_last_login(username)

def _restore_saved_company_files_for_authenticated_user() -> None:
    if not st.session_state.is_authenticated or not st.session_state.auth_username:
        st.session_state.saved_company_files = []
        return
    st.session_state.saved_company_files = list_company_files(st.session_state.auth_username)


def _handle_logout() -> None:
    token = st.session_state.auth_session_token
    invalidate_user_session(token)
    st.session_state.is_authenticated = False
    st.session_state.auth_username = ""
    st.session_state.auth_session_token = ""
    st.session_state.auth_initialized_user = ""
    _reset_user_runtime_state()


_restore_auth_from_cookie()
_restore_saved_company_files_for_authenticated_user()


def _parse_name_set(raw: str, fallback: set[str]) -> set[str]:
    names = {name.strip().lower() for name in (raw or "").split(",") if name.strip()}
    return names or fallback


def _super_admin_usernames() -> set[str]:
    return _parse_name_set(os.getenv("SUPER_ADMIN_USERNAMES", "admin"), {"admin"})


def _operator_usernames() -> set[str]:
    return _parse_name_set(os.getenv("OPERATOR_USERNAMES", "operator"), {"operator"})


def _legacy_admin_usernames() -> set[str]:
    # 하위 호환: 기존 ADMIN_USERNAMES 설정값도 운영자 권한으로 인정
    return _parse_name_set(os.getenv("ADMIN_USERNAMES", ""), set())


def _get_admin_role(username: str) -> str:
    normalized = str(username or "").strip().lower()
    if not normalized:
        return "user"
    if normalized in _super_admin_usernames():
        return "super_admin"
    if normalized in _operator_usernames() or normalized in _legacy_admin_usernames():
        return "operator"
    return "user"


def _can_view_admin_dashboard(username: str) -> bool:
    return _get_admin_role(username) in {"super_admin", "operator"}


def _can_manage_admin_settings(username: str) -> bool:
    return _get_admin_role(username) == "super_admin"


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _safe_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except ValueError:
        return float(default)


def _safe_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return int(default)


def _pdf_viewer_required() -> bool:
    # 로컬 기본값은 선택 모드(0), 배포에서는 환경변수로 1 권장
    raw = os.getenv("PDF_VIEWER_REQUIRED", "0").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def ensure_pdf_viewer_preflight() -> None:
    """
    PDF 뷰어 의존성 사전 점검.
    - 필수 모드(PDF_VIEWER_REQUIRED=1): 미설치 시 분석/렌더 차단
    - 선택 모드: 미설치 시 폴백 뷰어 허용
    """
    required = _pdf_viewer_required()
    module_available = importlib.util.find_spec("streamlit_pdf_viewer") is not None
    st.session_state.pdf_viewer_required = required
    st.session_state.pdf_viewer_available = module_available
    if required and not module_available:
        st.session_state.pdf_viewer_error = (
            "운영 설정 오류: `streamlit-pdf-viewer`가 설치되지 않았습니다. "
            "배포 환경 의존성(requirements.txt)을 확인해주세요."
        )
    else:
        st.session_state.pdf_viewer_error = ""


def _opinion_experiment_log_path() -> str:
    return os.getenv("OPINION_EXPERIMENT_LOG_PATH", "./reports/opinion_experiment.jsonl")


def log_opinion_experiment(event: str, mode: str, variant: str = "", extra: dict[str, Any] | None = None) -> None:
    """
    의견 실험(A/B/강도선택) 메타 로깅.
    원문 질의/민감정보는 저장하지 않는다.
    """
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": str(event or "").strip(),
        "mode": str(mode or "").strip().lower(),
        "variant": str(variant or "").strip().lower(),
        "username": str(st.session_state.get("auth_username", "") or ""),
    }
    if extra:
        payload.update(extra)
    path = _opinion_experiment_log_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _rows_to_csv_bytes(rows: list[dict], field_order: list[str] | None = None) -> bytes:
    if not rows:
        return b""
    fieldnames = field_order or sorted({key for row in rows for key in row.keys()})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return output.getvalue().encode("utf-8")


def _admin_alert_log_path() -> str:
    return os.getenv("ADMIN_ALERT_LOG_PATH", "./reports/admin_alerts.jsonl")


def load_router_analytics(log_path: str, window_days: int = 7, max_events: int = 5000) -> dict:
    now = datetime.now(timezone.utc)
    window_days = max(1, int(window_days))
    current_since = now - timedelta(days=window_days)
    previous_since = current_since - timedelta(days=window_days)
    events: list[dict] = []

    try:
        with open(log_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        if max_events > 0 and len(lines) > max_events:
            lines = lines[-max_events:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    except FileNotFoundError:
        pass

    total = len(events)
    current_window_events: list[dict] = []
    previous_window_events: list[dict] = []
    llm_called = 0
    for event in events:
        if bool(event.get("llm_called")):
            llm_called += 1
        parsed = _parse_iso_datetime(str(event.get("timestamp", "")))
        if parsed and parsed >= current_since:
            current_window_events.append(event)
        elif parsed and previous_since <= parsed < current_since:
            previous_window_events.append(event)

    policy_counts = Counter(str(event.get("policy", "UNKNOWN")) for event in events)
    intent_counts = Counter(str(event.get("intent", "UNKNOWN")) for event in events)
    window_policy_counts = Counter(str(event.get("policy", "UNKNOWN")) for event in current_window_events)
    window_intent_counts = Counter(str(event.get("intent", "UNKNOWN")) for event in current_window_events)

    failure_policies = {"ASK_CLARIFY", "BLOCK_INSUFFICIENT_CONTEXT", "BLOCK_UNSAFE"}

    def _rate(items: list[dict], predicate) -> float:
        if not items:
            return 0.0
        matched = sum(1 for item in items if predicate(item))
        return matched / len(items)

    current_block_rate = _rate(
        current_window_events,
        lambda item: str(item.get("policy", "")) == "BLOCK_OFFTOPIC",
    )
    previous_block_rate = _rate(
        previous_window_events,
        lambda item: str(item.get("policy", "")) == "BLOCK_OFFTOPIC",
    )
    current_failure_rate = _rate(
        current_window_events,
        lambda item: str(item.get("policy", "")) in failure_policies,
    )
    previous_failure_rate = _rate(
        previous_window_events,
        lambda item: str(item.get("policy", "")) in failure_policies,
    )

    recent_events: list[dict[str, str | float | int]] = []
    for event in reversed(events[-20:]):
        recent_events.append(
            {
                "timestamp": str(event.get("timestamp", "")),
                "intent": str(event.get("intent", "UNKNOWN")),
                "policy": str(event.get("policy", "UNKNOWN")),
                "confidence": float(event.get("confidence", 0.0) or 0.0),
                "relevance": float(event.get("relevance_score", 0.0) or 0.0),
                "query_hash": str(event.get("query_hash", "")),
            }
        )

    return {
        "log_path": log_path,
        "total_events": total,
        "window_days": window_days,
        "window_events": len(current_window_events),
        "previous_window_events": len(previous_window_events),
        "llm_called": llm_called,
        "policy_counts": dict(policy_counts),
        "intent_counts": dict(intent_counts),
        "window_policy_counts": dict(window_policy_counts),
        "window_intent_counts": dict(window_intent_counts),
        "current_block_rate": current_block_rate,
        "previous_block_rate": previous_block_rate,
        "current_failure_rate": current_failure_rate,
        "previous_failure_rate": previous_failure_rate,
        "recent_events": recent_events,
    }


def evaluate_router_alerts(router: dict) -> list[dict[str, str | float | int]]:
    """
    라우터 이상징후(차단율 급증/실패율 증가) 평가.
    """
    alerts: list[dict[str, str | float | int]] = []
    min_events = max(1, _safe_int_env("ADMIN_ALERT_MIN_EVENTS", 20))
    block_factor = max(1.0, _safe_float_env("ADMIN_ALERT_BLOCK_SPIKE_FACTOR", 1.8))
    block_delta = max(0.0, _safe_float_env("ADMIN_ALERT_BLOCK_ABS_DELTA", 0.1))
    failure_delta = max(0.0, _safe_float_env("ADMIN_ALERT_FAILURE_DELTA", 0.08))
    failure_threshold = max(0.0, _safe_float_env("ADMIN_ALERT_FAILURE_THRESHOLD", 0.35))

    current_total = int(router.get("window_events", 0))
    prev_total = int(router.get("previous_window_events", 0))
    current_block = float(router.get("current_block_rate", 0.0) or 0.0)
    prev_block = float(router.get("previous_block_rate", 0.0) or 0.0)
    current_fail = float(router.get("current_failure_rate", 0.0) or 0.0)
    prev_fail = float(router.get("previous_failure_rate", 0.0) or 0.0)

    if current_total >= min_events and prev_total >= min_events:
        if current_block >= max(prev_block * block_factor, prev_block + block_delta):
            alerts.append(
                {
                    "type": "block_rate_spike",
                    "severity": "high",
                    "message": "오프토픽 차단율이 이전 기간 대비 급증했습니다.",
                    "current_rate": current_block,
                    "previous_rate": prev_block,
                    "window_days": int(router.get("window_days", 7)),
                }
            )

    if current_total >= min_events and prev_total >= min_events:
        if (current_fail - prev_fail) >= failure_delta and current_fail >= failure_threshold:
            alerts.append(
                {
                    "type": "failure_rate_increase",
                    "severity": "medium",
                    "message": "질의 실패율(명확화/근거부족/차단)이 증가했습니다.",
                    "current_rate": current_fail,
                    "previous_rate": prev_fail,
                    "window_days": int(router.get("window_days", 7)),
                }
            )
    return alerts


def persist_admin_alerts(alerts: list[dict[str, str | float | int]]) -> None:
    """
    알림을 로컬 JSONL에 저장(중복 방지 쿨다운 적용).
    """
    if not alerts:
        return
    path = _admin_alert_log_path()
    cooldown_minutes = max(1, _safe_int_env("ADMIN_ALERT_COOLDOWN_MINUTES", 60))
    now = datetime.now(timezone.utc)

    recent_map: dict[str, datetime] = {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()[-200:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = str(payload.get("type", ""))
            ts = _parse_iso_datetime(str(payload.get("timestamp", "")))
            if key and ts:
                recent_map[key] = max(ts, recent_map.get(key, ts))
    except FileNotFoundError:
        pass

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for alert in alerts:
            key = str(alert.get("type", ""))
            last = recent_map.get(key)
            if last and (now - last).total_seconds() < cooldown_minutes * 60:
                continue
            payload = {
                "timestamp": now.isoformat(),
                **alert,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            recent_map[key] = now


def load_recent_admin_alerts(limit: int = 50) -> list[dict]:
    path = _admin_alert_log_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return []
    records: list[dict] = []
    for line in lines[-max(1, int(limit)):]:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return list(reversed(records))


# ============================================================
# STEP 3: 엔진 초기화
# ============================================================

def verify_openai_api_key(api_key: str) -> None:
    """OpenAI API 키 유효성 검증"""
    from openai import OpenAI

    verify_model = os.getenv("OPENAI_VERIFY_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    client.chat.completions.create(
        model=verify_model,
        max_tokens=1,
        temperature=0.0,
        messages=[{"role": "user", "content": "ping"}]
    )


def initialize_engines(api_key: str):
    """API 키 검증 후 세션 격리된 RAG 엔진 초기화"""
    from engine import RAGEngine

    # 키가 바뀐 경우에만 재검증
    if st.session_state.validated_api_key != api_key:
        verify_openai_api_key(api_key)
        st.session_state.validated_api_key = api_key

    # 로그인 사용자면 사용자 단위로 영속 컬렉션을 사용 (F5 이후 유지)
    if st.session_state.is_authenticated and st.session_state.auth_username:
        scope = username_to_scope(st.session_state.auth_username)
    else:
        scope = st.session_state.session_id

    company_collection = f"company_knowledge_{scope}"
    rfx_collection = f"rfx_knowledge_{scope}_{st.session_state.session_id}"

    if not st.session_state.company_rag_engine:
        st.session_state.company_rag_engine = RAGEngine(
            persist_directory="./data/vectordb",
            collection_name=company_collection
        )

    if not st.session_state.rfx_rag_engine:
        st.session_state.rfx_rag_engine = RAGEngine(
            persist_directory="./data/vectordb",
            collection_name=rfx_collection
        )

    # 기존 코드와의 하위 호환 (회사 KB)
    st.session_state.rag_engine = st.session_state.company_rag_engine

    # 로그인 사용자라면 저장된 회사 문서 목록/색인 상태 복원
    if st.session_state.is_authenticated and st.session_state.auth_username:
        username = st.session_state.auth_username
        st.session_state.saved_company_files = list_company_files(username)

        # 최초 1회만 사용자 저장 파일을 컬렉션에 복원 (컬렉션 비어있을 때)
        if st.session_state.auth_initialized_user != username:
            if st.session_state.company_rag_engine.collection.count() == 0:
                restored = 0
                for saved in st.session_state.saved_company_files:
                    if os.path.exists(saved.stored_path):
                        try:
                            restored += st.session_state.company_rag_engine.add_document(saved.stored_path)
                        except Exception:
                            # 개별 파일 오류는 건너뜀
                            continue
                if restored > 0:
                    st.session_state.company_docs_loaded = True
            else:
                st.session_state.company_docs_loaded = st.session_state.company_rag_engine.collection.count() > 0

            st.session_state.auth_initialized_user = username


# ============================================================
# STEP 4: PDF 하이라이트 연동 챗 처리
#
# 📌 이것이 ChatPDF/Adobe Acrobat AI의 핵심 메커니즘:
#    1. LLM에게 "근거 텍스트 + 페이지"를 함께 반환하도록 프롬프트
#    2. 응답에서 참조 정보 파싱
#    3. PyMuPDF로 해당 텍스트의 좌표 검색
#    4. streamlit-pdf-viewer에 어노테이션으로 전달
#    5. scroll_to_annotation으로 자동 이동
# ============================================================


def _get_env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "off", "no"}


def _collect_rag_scores(message: str) -> tuple[list[float], list[float]]:
    """회사/RFx RAG top-k 점수 수집 (라우팅 로깅/근거 게이트용)"""
    company_scores: list[float] = []
    rfx_scores: list[float] = []

    try:
        if (
            st.session_state.company_rag_engine
            and st.session_state.company_rag_engine.collection.count() > 0
        ):
            company_results = st.session_state.company_rag_engine.search(message, top_k=5)
            company_scores = [float(result.score or 0.0) for result in company_results]
    except Exception:
        company_scores = []

    try:
        if st.session_state.rfx_rag_engine and st.session_state.rfx_rag_engine.collection.count() > 0:
            rfx_results = st.session_state.rfx_rag_engine.search(message, top_k=5)
            rfx_scores = [float(result.score or 0.0) for result in rfx_results]
    except Exception:
        rfx_scores = []

    return company_scores, rfx_scores


def _max_relevance_score(company_scores: list[float], rfx_scores: list[float]) -> float:
    all_scores = company_scores + rfx_scores
    if not all_scores:
        return 0.0
    return max(all_scores)


def _has_any_context() -> bool:
    """현재 세션에 질의 가능한 문맥이 있는지 판정"""
    try:
        has_company = bool(
            st.session_state.company_rag_engine
            and st.session_state.company_rag_engine.collection.count() > 0
        )
    except Exception:
        has_company = False
    try:
        has_rfx = bool(
            st.session_state.rfx_rag_engine
            and st.session_state.rfx_rag_engine.collection.count() > 0
        )
    except Exception:
        has_rfx = False
    return has_company or has_rfx


def _update_last_route_state(decision: RouteDecision, relevance_score: float, has_context: bool) -> None:
    st.session_state.last_route_intent = decision.intent.value
    st.session_state.last_route_confidence = float(decision.confidence)
    st.session_state.last_route_policy = decision.policy.value
    st.session_state.last_route_reason = decision.reason
    st.session_state.last_relevance_score = float(relevance_score)
    st.session_state.last_context_available = bool(has_context)


def _route_chat_message(message: str) -> tuple[RouteDecision, list[float], list[float], float, float, bool]:
    """질의 라우팅 + 근거 문맥 정책 적용"""
    router_model = os.getenv("CHAT_ROUTER_MODEL", os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"))
    confidence_threshold = _get_env_float("CHAT_ROUTER_CONFIDENCE_THRESHOLD", 0.65)
    min_relevance_score = _get_env_float("CHAT_MIN_RELEVANCE_SCORE", 0.0)
    offtopic_strict = _get_env_bool("CHAT_OFFTOPIC_STRICT", True)

    decision = route_user_query(
        message=message,
        api_key=st.session_state.api_key,
        model=router_model,
        confidence_threshold=confidence_threshold,
        offtopic_strict=offtopic_strict,
    )

    company_scores, rfx_scores = _collect_rag_scores(message)
    relevance_score = _max_relevance_score(company_scores, rfx_scores)
    has_context = _has_any_context()

    decision = apply_context_policy(
        decision=decision,
        has_context=has_context,
        relevance_score=relevance_score,
        min_relevance_score=min_relevance_score,
    )
    _update_last_route_state(
        decision=decision,
        relevance_score=relevance_score,
        has_context=has_context,
    )

    write_router_telemetry(
        log_path=default_router_log_path(),
        message=message,
        decision=decision,
        company_scores=company_scores,
        rfx_scores=rfx_scores,
        relevance_score=relevance_score,
        min_relevance_score=min_relevance_score,
        has_context=has_context,
    )
    return (
        decision,
        company_scores,
        rfx_scores,
        relevance_score,
        min_relevance_score,
        has_context,
    )


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


def get_chat_response_with_references(message: str) -> tuple[str, list[dict]]:
    """
    챗봇 응답 + PDF 참조 정보를 함께 반환.

    왜 이렇게 하는가:
    ─────────────────
    일반 RAG 챗봇은 답변만 반환. 우리는 ChatPDF처럼
    "답변 + 어디서 찾았는지"를 함께 반환해야 함.

    방법:
    1. RAG 검색으로 관련 청크 + 페이지 번호 확보
    2. LLM에게 답변 시 참조 정보를 포함하도록 프롬프트
    3. 응답에서 참조 파싱 → 하이라이트 좌표 생성

    Returns:
        (answer_text, references)
        references = [{"page": 3, "text": "참조 텍스트"}, ...]
    """
    from openai import OpenAI

    api_key = st.session_state.api_key

    if not api_key:
        return ("⚠️ 운영자가 OPENAI_API_KEY를 설정하지 않았습니다.", [])

    # ── RAG 검색 ──
    company_context_text = ""
    rfx_context_text = ""
    pdf_references = []

    if (
        st.session_state.company_rag_engine and
        st.session_state.company_rag_engine.collection.count() > 0
    ):
        results = st.session_state.company_rag_engine.search(message, top_k=5)
        for r in results:
            page_num = r.metadata.get("page_number", -1)
            company_context_text += (
                f"\n[회사 출처: {r.source_file}, 페이지 {page_num}]\n{r.text}\n---\n"
            )

    if st.session_state.rfx_rag_engine and st.session_state.rfx_rag_engine.collection.count() > 0:
        results = st.session_state.rfx_rag_engine.search(message, top_k=5)
        for r in results:
            page_num = r.metadata.get("page_number", -1)
            if page_num <= 0:
                # source_file 패턴: RFx_<파일명>_p<페이지>
                import re
                match = re.search(r"_p(\d+)$", r.source_file)
                if match:
                    page_num = int(match.group(1))

            rfx_context_text += f"\n[RFx 출처: {r.source_file}, 페이지 {page_num}]\n{r.text}\n---\n"
            if page_num > 0:
                pdf_references.append({
                    "page": page_num,
                    "text": r.text[:100]  # 첫 100자
                })

    # ── RFx 분석 결과 컨텍스트 ──
    rfx_context = ""
    if st.session_state.rfx_analysis:
        rfx = st.session_state.rfx_analysis
        rfx_context = f"""
RFx 분석 결과:
- 공고명: {rfx.title}
- 발주기관: {rfx.issuing_org}
- 마감일: {rfx.deadline}
- 자격요건: {len(rfx.requirements)}개
"""

    matching_context = ""
    if st.session_state.matching_result:
        mr = st.session_state.matching_result
        eval_line = ""
        if mr.evaluation_available and mr.evaluation_total_score > 0:
            eval_line = f"- 평가예상점수: {mr.evaluation_expected_score:.1f}/{mr.evaluation_total_score:.1f}\n"
        matching_context = f"""
자격 매칭 결과:
- 종합 적합도: {mr.overall_score:.0f}%
- 추천: {mr.recommendation}
- 충족: {mr.met_count}개, 부분충족: {mr.partially_met_count}개, 미충족: {mr.not_met_count}개
{eval_line}"""

    # ── LLM 프롬프트 (구조화 JSON 우선) ──
    system_prompt = """당신은 입찰 전문 AI 어시스턴트입니다.
회사 정보와 RFx 문서를 바탕으로 입찰 관련 질문에 답변합니다.

반드시 JSON 객체만 반환하세요. 코드블록/설명 문구 금지.
스키마:
{
  "answer": "한국어 답변 문자열",
  "references": [
    {"page": 3, "text": "RFx 원문에서 발췌한 근거 텍스트"}
  ]
}

중요 규칙:
1. references.page는 RFx 원문 문서의 실제 페이지 번호만 사용하세요.
2. references.text는 RFx 원문에서 그대로 복사한 연속 구간(가능하면 12~80자)만 사용하세요.
3. 의역/요약/재서술 금지. 원문에 없는 단어를 references.text에 넣지 마세요.
4. 같은 문장 전체를 길게 넣지 말고, 검색 가능한 핵심 구절 1개만 넣으세요.
5. references는 최대 5개로 제한하세요.
6. answer에는 필요한 경우 [📄 p.X "핵심구절"] 인라인 표기 가능.
7. references.text는 반드시 [RFx 원문 (RAG 검색 결과)] 블록에서만 뽑으세요.
8. 회사 정보 블록 문구를 references.text에 사용하면 안 됩니다.
9. 한국어로 답변하세요."""

    user_prompt = f"""질문: {message}

{f'[회사 정보 (RAG 검색 결과)]{chr(10)}{company_context_text}' if company_context_text else '[회사 정보: 등록되지 않음]'}

{f'[RFx 원문 (RAG 검색 결과)]{chr(10)}{rfx_context_text}' if rfx_context_text else '[RFx 원문: 등록되지 않음]'}

{rfx_context}
{matching_context}

위 정보를 바탕으로 질문에 답변해주세요.
반드시 JSON 객체로 응답하세요."""

    try:
        chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=chat_model,
            max_tokens=2048,
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "kira_streamlit_chat_response",
                    "strict": True,
                    "schema": CHAT_RESPONSE_JSON_SCHEMA,
                },
            },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        full_response = (response.choices[0].message.content or "").strip()

        payload = json.loads(full_response)
        display_text = str(payload.get("answer", "")).strip()
        raw_refs = payload.get("references", [])
        references = raw_refs if isinstance(raw_refs, list) else []

        # RFx 문맥 기반 참조 필터링 (회사 문맥 오염 방지)
        def _normalize_ref_text(text: str) -> str:
            import re
            normalized = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", text or "").lower()
            normalized = re.sub(r"\s+", " ", normalized).strip()
            return normalized

        def _is_grounded_in_rfx(ref: dict) -> bool:
            page = int(ref.get("page", 0) or 0)
            if page <= 0:
                return False
            snippet = str(ref.get("text", "")).strip()
            if not snippet:
                return True  # page-only 참조는 허용

            snippet_norm = _normalize_ref_text(snippet)
            rfx_norm = _normalize_ref_text(rfx_context_text)
            if not snippet_norm or not rfx_norm:
                return False
            if snippet_norm in rfx_norm:
                return True

            keywords = [tok for tok in snippet_norm.split() if len(tok) >= 2][:6]
            hit_count = sum(1 for tok in keywords if tok in rfx_norm)
            return hit_count >= 2

        references = [ref for ref in references if _is_grounded_in_rfx(ref)]

        # RFx RAG 검색 결과의 페이지 정보를 보조로 활용
        # (회사 KB 페이지는 RFx PDF와 불일치할 수 있으므로 제외)
        if not references and pdf_references:
            references = pdf_references[:3]

        return (display_text, references)

    except Exception as e:
        return (f"❌ 응답 생성 실패: {e}", [])


def process_chat_with_highlights(message: str):
    """
    채팅 메시지 처리 + PDF 하이라이트 업데이트.

    전체 흐름:
    ──────────
    1. 사용자 메시지 저장
    2. LLM 응답 + 참조 정보 획득
    3. 참조 텍스트를 PDF에서 검색 → 좌표 획득
    4. 하이라이트 어노테이션 생성
    5. 자동 스크롤 대상 설정
    """
    # 1. 사용자 메시지 저장
    st.session_state.chat_history.append({"role": "user", "content": message})

    # 2. 질의 라우팅 + 정책 판정
    decision, _, _, _, _, _ = _route_chat_message(message)

    if decision.policy != ChatPolicy.ALLOW:
        response = build_policy_response(decision)
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": response,
                "references": [],
                "route_policy": decision.policy.value,
                "route_intent": decision.intent.value,
                "route_reason": decision.reason,
                "suggested_questions": decision.suggested_questions[:4],
            }
        )
        return

    # 3. 서버 API 키 체크 (ALLOW 경로에서만 필요)
    if not st.session_state.api_key:
        response = "⚠️ 운영자가 OPENAI_API_KEY를 설정하지 않았습니다."
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        return

    # 4. LLM 응답 + 참조 정보 획득
    response_text, references = get_chat_response_with_references(message)

    # 5. PDF 하이라이트 업데이트
    if references and st.session_state.highlight_manager:
        hm = st.session_state.highlight_manager

        # 이전 하이라이트 클리어 → 최신 답변의 참조만 표시
        hm.clear_highlights()

        # 참조 텍스트를 PDF에서 검색 → 좌표 획득 → 어노테이션 생성
        new_highlights = hm.add_highlights_from_references(references)

        # 세션 상태 업데이트
        st.session_state.current_annotations = hm.get_annotations()
        st.session_state.scroll_to_page = hm.get_scroll_target_page()
        st.session_state.scroll_to_annotation = hm.get_scroll_target_annotation()
        st.session_state.current_references = references

        # 하이라이트 결과를 답변에 추가
        if new_highlights:
            pages = sorted(set(h.page for h in new_highlights))
            page_str = ", ".join([f"p.{p}" for p in pages])
            response_text += f"\n\n---\n📍 **참조 위치**: {page_str} (오른쪽 PDF에 노란색 하이라이트 표시됨)"

    # 6. 응답 저장
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": response_text,
        "references": references,
        "route_policy": decision.policy.value,
        "route_intent": decision.intent.value,
        "route_reason": decision.reason,
    })


# ============================================================
# STEP 5: 사이드바 - 설정 & 문서 업로드
# ============================================================

def render_sidebar():
    """사이드바: 계정, 설정, 회사정보, 분석 문서 업로드"""

    ensure_pdf_viewer_preflight()

    with st.sidebar:
        if st.session_state.pdf_viewer_required and not st.session_state.pdf_viewer_available:
            st.error(st.session_state.pdf_viewer_error)
            st.caption(
                "운영 환경에서 `pip install -r requirements.txt`로 의존성을 복구한 뒤 재시작하세요."
            )
            st.divider()

        st.markdown("## 👤 계정")

        if not st.session_state.is_authenticated:
            st.markdown("### M&S 데이터웍스 Kira")
            st.caption("Google 또는 Kakao 소셜 로그인으로 시작하세요.")
            google_url = _social_login_url("google")
            kakao_url = _social_login_url("kakao")
            if not google_url or not kakao_url:
                st.error("소셜 로그인 URL이 설정되지 않았습니다. 운영자에게 문의하세요.")
                st.code(
                    "\n".join(
                        [
                            "SOCIAL_LOGIN_GOOGLE_URL=...",
                            "SOCIAL_LOGIN_KAKAO_URL=...",
                        ]
                    ),
                    language="bash",
                )
            else:
                st.link_button("🔐 Google로 시작", google_url, use_container_width=True)
                st.link_button("💬 Kakao로 시작", kakao_url, use_container_width=True)
            st.info("로그인 후 업로드한 회사 문서는 계정에 저장되어 F5 이후에도 유지됩니다.")
            return

        _restore_saved_company_files_for_authenticated_user()
        st.success(f"로그인: {st.session_state.auth_username}")
        admin_role = _get_admin_role(st.session_state.auth_username)
        if admin_role == "super_admin":
            st.info("👑 슈퍼관리자 권한으로 접속 중")
        elif admin_role == "operator":
            st.info("🛠 운영자 권한으로 접속 중")
        if st.button("🚪 로그아웃", use_container_width=True, key="btn_logout"):
            _handle_logout()
            st.rerun()
        logout_url = _social_logout_url()
        if logout_url:
            st.link_button("🔒 SSO 세션 종료", logout_url, use_container_width=True)

        st.divider()
        st.markdown("## ⚙️ 설정")
        env_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not env_api_key:
            st.error("운영 설정 오류: OPENAI_API_KEY가 설정되지 않았습니다.")
            st.code("OPENAI_API_KEY=...", language="bash")
            return

        st.session_state.api_key = env_api_key
        try:
            initialize_engines(env_api_key)
            st.caption("✅ 서버 내장 OpenAI 키로 연결됨")
        except Exception as e:
            st.error(f"❌ OpenAI 연결 실패: {e}")
            return

        st.divider()

        # ── 회사 정보 업로드 ──
        st.markdown("## 🏢 회사 정보")
        company_files = st.file_uploader(
            "회사 문서 업로드",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            key="company_uploader"
        )

        if company_files and st.button("📤 등록", type="primary", key="btn_company"):
            if not st.session_state.api_key:
                st.warning("운영자가 OPENAI_API_KEY를 설정해야 업로드할 수 있습니다.")
                return

            with st.spinner("처리 중..."):
                total = 0
                for file in company_files:
                    input_path = None
                    try:
                        file_bytes = file.read()
                        if st.session_state.is_authenticated and st.session_state.auth_username:
                            saved = save_company_file(
                                username=st.session_state.auth_username,
                                original_name=file.name,
                                content=file_bytes,
                            )
                            input_path = saved.stored_path
                        else:
                            with tempfile.NamedTemporaryFile(
                                delete=False, suffix=os.path.splitext(file.name)[1]
                            ) as tmp:
                                tmp.write(file_bytes)
                                input_path = tmp.name

                        count = st.session_state.company_rag_engine.add_document(input_path)
                        total += count
                        st.success(f"✅ {file.name}: {count}개 청크")
                    except Exception as e:
                        st.error(f"❌ {file.name}: {e}")
                    finally:
                        if input_path and os.path.exists(input_path):
                            # 로그인 사용자는 영속 파일이므로 삭제하지 않음
                            if not (st.session_state.is_authenticated and st.session_state.auth_username):
                                os.unlink(input_path)

                if total > 0:
                    st.session_state.company_docs_loaded = True
                    if st.session_state.is_authenticated and st.session_state.auth_username:
                        st.session_state.saved_company_files = list_company_files(st.session_state.auth_username)
                    st.success(f"🎉 총 {total}개 청크 등록!")

        # 직접 입력
        with st.expander("✏️ 직접 입력"):
            company_text = st.text_area("회사 정보", height=150, key="company_text_input")
            if company_text and st.button("📝 등록", key="btn_text"):
                if st.session_state.company_rag_engine:
                    count = st.session_state.company_rag_engine.add_text_directly(company_text, "직접입력")
                    if st.session_state.is_authenticated and st.session_state.auth_username:
                        text_name = f"직접입력_{uuid.uuid4().hex[:8]}.txt"
                        save_company_file(
                            username=st.session_state.auth_username,
                            original_name=text_name,
                            content=company_text.encode("utf-8"),
                        )
                        st.session_state.saved_company_files = list_company_files(st.session_state.auth_username)
                    st.session_state.company_docs_loaded = True
                    st.success(f"✅ {count}개 청크 등록!")

        saved_count = count_company_files(st.session_state.auth_username)
        vector_count = 0
        if st.session_state.company_rag_engine:
            try:
                vector_count = int(st.session_state.company_rag_engine.collection.count())
            except Exception:
                vector_count = 0
        st.info(f"📚 회사 문서 분석 준비: 근거 조각 {vector_count}개 · 저장 문서 {saved_count}개")

        if st.session_state.saved_company_files:
            with st.expander("💾 저장된 회사 문서", expanded=True):
                for idx, saved in enumerate(st.session_state.saved_company_files[:30], start=1):
                    st.caption(f"{idx}. {saved.original_name} ({saved.uploaded_at[:10]})")

        col_actions_1, col_actions_2 = st.columns(2)
        with col_actions_1:
            if st.button("🔄 저장 문서 재색인", key="btn_reindex_saved", use_container_width=True):
                if not st.session_state.company_rag_engine:
                    st.warning("RAG 엔진이 아직 준비되지 않았습니다. 운영 설정을 확인해주세요.")
                else:
                    with st.spinner("저장 문서 재색인 중..."):
                        st.session_state.company_rag_engine.clear_collection()
                        restored = 0
                        for saved in st.session_state.saved_company_files:
                            if os.path.exists(saved.stored_path):
                                try:
                                    restored += st.session_state.company_rag_engine.add_document(saved.stored_path)
                                except Exception:
                                    continue
                        st.session_state.company_docs_loaded = restored > 0
                        st.success(f"재색인 완료: 근거 조각 {restored}개")

        with col_actions_2:
            if st.button("🗑️ 문서 초기화", key="btn_delete_company_docs", use_container_width=True):
                now = datetime.now(timezone.utc)
                cooldown_seconds = max(10, _safe_int_env("COMPANY_DOC_DELETE_COOLDOWN_SECONDS", 60))
                last_raw = st.session_state.get("delete_last_executed_at", "")
                last_dt = _parse_iso_datetime(str(last_raw)) if last_raw else None
                if last_dt and (now - last_dt).total_seconds() < cooldown_seconds:
                    wait_seconds = int(cooldown_seconds - (now - last_dt).total_seconds())
                    st.warning(f"초기화는 {cooldown_seconds}초에 1회만 가능합니다. {wait_seconds}초 후 다시 시도하세요.")
                else:
                    armed_raw = st.session_state.get("delete_confirm_armed_at", "")
                    armed_dt = _parse_iso_datetime(str(armed_raw)) if armed_raw else None
                    if not armed_dt or (now - armed_dt).total_seconds() > 120:
                        st.session_state.delete_confirm_armed_at = now.isoformat()
                        st.warning("한 번 더 누르면 회사 문서가 모두 삭제됩니다. (2분 내 확인)")
                    else:
                        delete_result = delete_company_files(st.session_state.auth_username)
                        if st.session_state.company_rag_engine:
                            st.session_state.company_rag_engine.clear_collection()
                        st.session_state.saved_company_files = []
                        st.session_state.company_docs_loaded = False
                        st.session_state.delete_confirm_armed_at = ""
                        st.session_state.delete_last_executed_at = now.isoformat()
                        st.success(
                            "문서 초기화 완료: "
                            f"DB {delete_result['db_deleted']}건, 파일 {delete_result['file_deleted']}건 삭제"
                        )

        st.divider()

        # ── 분석 대상 문서 업로드 ──
        st.markdown("## 📄 분석할 문서")
        rfx_file = st.file_uploader(
            "분석할 문서 업로드",
            type=["pdf", "docx", "txt"],
            key="rfx_uploader"
        )

        if rfx_file and st.button("🔍 분석 시작", type="primary", key="btn_rfx"):
            if st.session_state.pdf_viewer_required and not st.session_state.pdf_viewer_available:
                st.error("분석을 시작할 수 없습니다. PDF 뷰어 의존성이 누락되었습니다.")
                return
            if not st.session_state.api_key:
                st.warning("운영자가 OPENAI_API_KEY를 설정해야 분석을 시작할 수 있습니다.")
                return

            with st.spinner("문서 분석 중입니다... 문서 길이에 따라 수 분이 걸릴 수 있습니다."):
                # 이전 RFx 결과/하이라이트 상태 초기화
                st.session_state.rfx_analysis = None
                st.session_state.matching_result = None
                st.session_state.rfx_loaded = False
                st.session_state.current_annotations = []
                st.session_state.current_references = []
                st.session_state.scroll_to_page = None
                st.session_state.scroll_to_annotation = None

                # PDF 바이너리 저장 (뷰어용)
                rfx_bytes = rfx_file.read()
                rfx_file.seek(0)  # 리셋

                # 🆕 PDF 뷰어용 데이터 저장
                if rfx_file.name.lower().endswith('.pdf'):
                    st.session_state.pdf_bytes = rfx_bytes
                    st.session_state.pdf_filename = rfx_file.name

                    # HighlightManager 초기화
                    st.session_state.highlight_manager = HighlightManager(
                        pdf_bytes=rfx_bytes
                    )
                else:
                    st.session_state.pdf_bytes = None
                    st.session_state.pdf_filename = ""
                    st.session_state.highlight_manager = None

                # 임시 파일로 저장 후 분석
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=os.path.splitext(rfx_file.name)[1]
                ) as tmp:
                    tmp.write(rfx_bytes)
                    tmp_path = tmp.name

                try:
                    from rfx_analyzer import RFxAnalyzer, RFxParseError

                    analyzer = RFxAnalyzer(api_key=st.session_state.api_key)
                    st.session_state.rfx_analysis = analyzer.analyze(tmp_path)
                    st.session_state.rfx_loaded = True

                    # RFx 원문도 별도 RAG에 추가 (회사 KB와 분리)
                    if st.session_state.rfx_rag_engine:
                        st.session_state.rfx_rag_engine.clear_collection()

                        if st.session_state.highlight_manager:
                            hm = st.session_state.highlight_manager
                            page_texts = hm.highlighter.get_all_text_with_pages()
                            for pt in page_texts:
                                st.session_state.rfx_rag_engine.add_text_directly(
                                    pt["text"],
                                    source_name=f"RFx_{rfx_file.name}_p{pt['page']}",
                                    base_metadata={"page_number": pt["page"], "type": "rfx_text"}
                                )
                        else:
                            from document_parser import DocumentParser

                            parsed = DocumentParser().parse(tmp_path)
                            if parsed.pages:
                                for page_idx, page_text in enumerate(parsed.pages, start=1):
                                    st.session_state.rfx_rag_engine.add_text_directly(
                                        page_text,
                                        source_name=f"RFx_{rfx_file.name}_p{page_idx}",
                                        base_metadata={"page_number": page_idx, "type": "rfx_text"}
                                    )
                            elif parsed.text:
                                st.session_state.rfx_rag_engine.add_text_directly(
                                    parsed.text,
                                    source_name=f"RFx_{rfx_file.name}",
                                    base_metadata={"page_number": -1, "type": "rfx_text"}
                                )

                    st.success("✅ 문서 분석 완료!")

                    # 자격 매칭
                    if st.session_state.company_docs_loaded:
                        from matcher import QualificationMatcher
                        matcher = QualificationMatcher(
                            rag_engine=st.session_state.company_rag_engine,
                            api_key=st.session_state.api_key
                        )
                        st.session_state.matching_result = matcher.match(
                            st.session_state.rfx_analysis
                        )
                        st.success("✅ 요건 매칭 완료!")

                except RFxParseError as e:
                    st.error(f"❌ RFx 구조화 추출 실패: {e}")
                    st.info("문서를 다시 업로드하거나 PDF OCR 품질을 확인해주세요.")
                except Exception as e:
                    st.error(f"❌ 분석 실패: {e}")
                finally:
                    os.unlink(tmp_path)


# ============================================================
# STEP 6: 메인 레이아웃 (Split View)
#
# 📌 ChatPDF / Adobe Acrobat AI 핵심 UX 패턴:
#    [왼쪽 50%: 챗봇]  |  [오른쪽 50%: PDF 뷰어]
#    답변의 참조를 클릭 → PDF 자동 스크롤 + 하이라이트
# ============================================================

def render_main():
    """메인 페이지: Split Layout"""
    ensure_pdf_viewer_preflight()

    if not st.session_state.is_authenticated:
        st.markdown(
            '<p class="main-header">M&S 데이터웍스 | Kira 문서 분석 어시스턴트</p>',
            unsafe_allow_html=True
        )
        st.markdown(
            """
            <div class="kira-section-card">
              <h3 style="margin-bottom:8px;">복잡한 입찰/제안 문서를 근거 기반으로 빠르게 판단하세요.</h3>
              <p style="margin-bottom:8px;">왼쪽 사이드바에서 Google 또는 Kakao 로그인 후 바로 시작할 수 있습니다.</p>
              <p style="color:#4A5B75;">로그인 후 업로드한 회사 문서는 계정에 안전하게 저장되며 F5 이후에도 유지됩니다.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.session_state.pdf_viewer_required and not st.session_state.pdf_viewer_available:
            st.error(st.session_state.pdf_viewer_error)
        return

    st.markdown(
        '<p class="main-header">M&S 데이터웍스 | Kira 문서 분석 어시스턴트</p>',
        unsafe_allow_html=True
    )

    if st.session_state.pdf_viewer_required and not st.session_state.pdf_viewer_available:
        st.error(st.session_state.pdf_viewer_error)
        st.caption("운영 설정 오류가 해결되기 전까지 분석 시작이 차단됩니다.")

    # ── 상단 상태 바 ──
    render_status_bar()

    # ── PDF가 업로드되었으면 Split View, 아니면 Full Chat ──
    if st.session_state.pdf_bytes:
        render_split_view()
    else:
        render_full_chat_view()

    # ── 관리자 전용 운영 지표 ──
    if _can_view_admin_dashboard(st.session_state.auth_username):
        render_admin_dashboard()


def _route_intent_label(intent_value: str) -> str:
    labels = {
        RouteIntent.DOMAIN_RFX.value: "입찰 도메인",
        RouteIntent.DOC_QA.value: "문서 질의",
        RouteIntent.SMALL_TALK_OFFTOPIC.value: "오프토픽",
        RouteIntent.UNKNOWN.value: "의도 불명확",
        RouteIntent.UNSAFE.value: "안전 차단",
    }
    return labels.get(str(intent_value or ""), "미분류")


def render_status_bar():
    """상단 상태 표시 바"""
    intent_label = _route_intent_label(st.session_state.last_route_intent)
    confidence = float(st.session_state.last_route_confidence or 0.0)
    relevance_score = float(st.session_state.last_relevance_score or 0.0)
    evidence_label = "근거충분" if st.session_state.last_context_available else "근거부족"

    if st.session_state.matching_result:
        score = st.session_state.matching_result.overall_score
        score_label = f"{score:.0f}%"
    else:
        score_label = "—"

    status_html = f"""
    <div class="kira-status-grid">
      <div class="kira-status-card">
        <div class="kira-status-label">회사 정보</div>
        <div class="kira-status-value">{'✅ 등록됨' if st.session_state.company_docs_loaded else '⬜ 미등록'}</div>
      </div>
      <div class="kira-status-card">
        <div class="kira-status-label">문서 분석</div>
        <div class="kira-status-value">{'✅ 완료' if st.session_state.rfx_loaded else '⬜ 미완료'}</div>
      </div>
      <div class="kira-status-card">
        <div class="kira-status-label">적합도</div>
        <div class="kira-status-value">{score_label}</div>
      </div>
      <div class="kira-status-card">
        <div class="kira-status-label">질의유형</div>
        <div class="kira-status-value">{intent_label} ({confidence:.0%})</div>
      </div>
      <div class="kira-status-card">
        <div class="kira-status-label">근거상태</div>
        <div class="kira-status-value">{evidence_label} · score {relevance_score:.2f}</div>
      </div>
    </div>
    """
    st.markdown(status_html, unsafe_allow_html=True)
    if st.session_state.last_route_reason:
        st.caption(f"라우팅 근거: {st.session_state.last_route_reason}")


def render_admin_dashboard() -> None:
    """관리자 전용 운영 지표 패널"""
    username = st.session_state.auth_username
    if not _can_view_admin_dashboard(username):
        return
    role = _get_admin_role(username)
    can_manage = _can_manage_admin_settings(username)

    period_options = [7, 30, 90]
    if "admin_kpi_days" not in st.session_state:
        st.session_state.admin_kpi_days = 7

    st.divider()
    with st.expander("🛠 관리자 대시보드", expanded=False):
        st.caption("운영 지표는 사용자 DB + 라우터 텔레메트리 로그 기반으로 집계됩니다.")
        st.caption(f"현재 권한: `{role}`")
        period_days = st.radio(
            "KPI 기간",
            options=period_options,
            horizontal=True,
            key="admin_kpi_days",
            format_func=lambda day: f"{day}일",
        )

        overview = get_admin_overview(days=period_days)
        usage_overview = get_usage_overview()
        router = load_router_analytics(
            log_path=default_router_log_path(),
            window_days=period_days,
            max_events=5000,
        )
        alerts = evaluate_router_alerts(router)

        auto_persist_alerts = _get_env_bool("ADMIN_ALERT_AUTO_PERSIST", True)
        if alerts and can_manage and auto_persist_alerts:
            persist_admin_alerts(alerts)
        recent_alerts = load_recent_admin_alerts(limit=50)

        total_events = int(router.get("total_events", 0))
        window_events = int(router.get("window_events", 0))
        llm_called = int(router.get("llm_called", 0))
        llm_call_rate = (llm_called / total_events * 100.0) if total_events else 0.0
        offtopic_block_rate = float(router.get("current_block_rate", 0.0) or 0.0) * 100.0
        failure_rate = float(router.get("current_failure_rate", 0.0) or 0.0) * 100.0

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("회원 수", f"{overview['total_users']}")
        with col2:
            st.metric("활성 세션", f"{overview['active_sessions']}")
        with col3:
            st.metric("회사 문서", f"{overview['total_files']}")
        with col4:
            st.metric(f"{overview['window_days']}일 활성 사용자", f"{overview['active_users_window']}")
        with col5:
            st.metric(f"{period_days}일 이벤트", f"{window_events}")
        with col6:
            st.metric("오프토픽 차단율", f"{offtopic_block_rate:.1f}%")
        st.caption(
            "사용량 요약: "
            f"오늘 채팅 {usage_overview['today_chat']}회 / 분석 {usage_overview['today_analyze']}회 · "
            f"이번달 채팅 {usage_overview['month_chat']}회 / 분석 {usage_overview['month_analyze']}회"
        )

        if alerts:
            for alert in alerts:
                msg = str(alert.get("message", "임계치 알림"))
                current = float(alert.get("current_rate", 0.0) or 0.0) * 100.0
                previous = float(alert.get("previous_rate", 0.0) or 0.0) * 100.0
                alert_line = (
                    f"🚨 {msg} (현재 {current:.1f}% / 이전 {previous:.1f}%, "
                    f"윈도우 {int(alert.get('window_days', period_days))}일)"
                )
                if str(alert.get("severity", "")).lower() == "high":
                    st.error(alert_line)
                else:
                    st.warning(alert_line)

        tab_users, tab_files, tab_usage, tab_router, tab_alerts, tab_system = st.tabs(
            ["👥 사용자", "📎 업로드", "📈 사용량", "🧭 라우터", "🚨 알림", "⚙️ 시스템"]
        )

        with tab_users:
            rows = list_user_activity(limit=100)
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("표시할 사용자 활동 데이터가 없습니다.")
            users_csv = _rows_to_csv_bytes(
                rows or [{"username": "", "created_at": "", "last_login_at": "", "file_count": 0}],
                field_order=["username", "created_at", "last_login_at", "file_count"],
            )
            st.download_button(
                "📥 사용자 활동 CSV",
                data=users_csv,
                file_name=f"admin_users_{period_days}d.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with tab_files:
            uploads = list_recent_company_files(limit=100)
            for item in uploads:
                item["size_kb"] = round(float(item.get("size_bytes", 0)) / 1024.0, 2)
            if uploads:
                st.dataframe(uploads, use_container_width=True)
            else:
                st.info("표시할 업로드 기록이 없습니다.")
            upload_csv = _rows_to_csv_bytes(
                uploads or [{
                    "username": "",
                    "original_name": "",
                    "file_ext": "",
                    "uploaded_at": "",
                    "size_bytes": 0,
                    "size_kb": 0.0,
                }],
                field_order=["username", "original_name", "file_ext", "uploaded_at", "size_bytes", "size_kb"],
            )
            st.download_button(
                "📥 업로드 기록 CSV",
                data=upload_csv,
                file_name=f"admin_uploads_{period_days}d.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with tab_usage:
            rows = list_usage_by_actor(limit=300)
            uc1, uc2, uc3 = st.columns(3)
            with uc1:
                st.metric("오늘 채팅", f"{usage_overview['today_chat']}")
            with uc2:
                st.metric("오늘 분석", f"{usage_overview['today_analyze']}")
            with uc3:
                st.metric("오늘 활성 사용자/세션", f"{usage_overview['active_actors_today']}")
            uc4, uc5, uc6 = st.columns(3)
            with uc4:
                st.metric("이번달 채팅", f"{usage_overview['month_chat']}")
            with uc5:
                st.metric("이번달 분석", f"{usage_overview['month_analyze']}")
            with uc6:
                st.metric("이번달 활성 사용자/세션", f"{usage_overview['active_actors_month']}")
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("사용량 데이터가 아직 없습니다.")
            usage_csv = _rows_to_csv_bytes(
                rows or [{
                    "actor_key": "",
                    "username": "",
                    "today_chat": 0,
                    "today_analyze": 0,
                    "month_chat": 0,
                    "month_analyze": 0,
                    "last_event_at": "",
                }],
                field_order=[
                    "actor_key",
                    "username",
                    "today_chat",
                    "today_analyze",
                    "month_chat",
                    "month_analyze",
                    "last_event_at",
                ],
            )
            st.download_button(
                "📥 사용량 CSV",
                data=usage_csv,
                file_name=f"admin_usage_{period_days}d.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with tab_router:
            st.markdown(
                f"- 최근 {router['window_days']}일 이벤트: **{router['window_events']}건**\n"
                f"- 이전 {router['window_days']}일 이벤트: **{router['previous_window_events']}건**\n"
                f"- LLM 라우터 호출률(전체): **{llm_call_rate:.1f}%**\n"
                f"- 실패 정책 비율(현재 윈도우): **{failure_rate:.1f}%**"
            )
            policy_rows = [
                {"policy": key, "count": value}
                for key, value in sorted(
                    router.get("policy_counts", {}).items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            ]
            intent_rows = [
                {"intent": key, "count": value}
                for key, value in sorted(
                    router.get("intent_counts", {}).items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            ]
            colp, coli = st.columns(2)
            with colp:
                st.markdown("**정책 분포(전체)**")
                st.dataframe(policy_rows or [{"policy": "N/A", "count": 0}], use_container_width=True)
                st.download_button(
                    "📥 정책 분포 CSV",
                    data=_rows_to_csv_bytes(policy_rows or [{"policy": "N/A", "count": 0}], ["policy", "count"]),
                    file_name=f"router_policy_distribution_{period_days}d.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_download_router_policy_csv",
                )
            with coli:
                st.markdown("**의도 분포(전체)**")
                st.dataframe(intent_rows or [{"intent": "N/A", "count": 0}], use_container_width=True)
                st.download_button(
                    "📥 의도 분포 CSV",
                    data=_rows_to_csv_bytes(intent_rows or [{"intent": "N/A", "count": 0}], ["intent", "count"]),
                    file_name=f"router_intent_distribution_{period_days}d.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_download_router_intent_csv",
                )

            recent_events = router.get("recent_events", [])
            if recent_events:
                st.markdown("**최근 라우터 이벤트 20건**")
                st.dataframe(recent_events, use_container_width=True)
                st.download_button(
                    "📥 최근 라우터 이벤트 CSV",
                    data=_rows_to_csv_bytes(recent_events),
                    file_name=f"router_recent_events_{period_days}d.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_download_router_recent_csv",
                )
            else:
                st.info("라우터 로그가 아직 없습니다.")

        with tab_alerts:
            st.markdown("**임계치 알림 상태**")
            st.markdown(
                f"- 자동 기록: **{'ON' if auto_persist_alerts else 'OFF'}**\n"
                f"- 최소 이벤트 수: **{_safe_int_env('ADMIN_ALERT_MIN_EVENTS', 20)}**\n"
                f"- 차단율 급증 계수/절대증가: **{_safe_float_env('ADMIN_ALERT_BLOCK_SPIKE_FACTOR', 1.8):.2f} / {_safe_float_env('ADMIN_ALERT_BLOCK_ABS_DELTA', 0.1):.2f}**\n"
                f"- 실패율 증가 임계: **{_safe_float_env('ADMIN_ALERT_FAILURE_DELTA', 0.08):.2f} / {_safe_float_env('ADMIN_ALERT_FAILURE_THRESHOLD', 0.35):.2f}**"
            )
            if can_manage and st.button("🔔 지금 임계치 재평가 + 저장", key="btn_admin_alert_manual"):
                persist_admin_alerts(alerts)
                recent_alerts = load_recent_admin_alerts(limit=50)
                st.success("알림 로그를 업데이트했습니다.")

            if recent_alerts:
                st.markdown("**최근 알림 로그**")
                st.dataframe(recent_alerts, use_container_width=True)
                st.download_button(
                    "📥 알림 로그 CSV",
                    data=_rows_to_csv_bytes(recent_alerts),
                    file_name="admin_alerts_recent.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_download_admin_alerts_csv",
                )
            else:
                st.info("기록된 알림이 없습니다.")

        with tab_system:
            st.markdown("**운영 설정**")
            st.code(
                "\n".join(
                    [
                        f"CHAT_ROUTER_LOG_PATH={router['log_path']}",
                        f"SUPER_ADMIN_USERNAMES={os.getenv('SUPER_ADMIN_USERNAMES', 'admin')}",
                        f"OPERATOR_USERNAMES={os.getenv('OPERATOR_USERNAMES', 'operator')}",
                        f"ADMIN_USERNAMES={os.getenv('ADMIN_USERNAMES', '')}",
                        f"ADMIN_ALERT_LOG_PATH={_admin_alert_log_path()}",
                        f"AUTH_COOKIE_SECURE={os.getenv('AUTH_COOKIE_SECURE', '0')}",
                    ]
                ),
                language="bash",
            )
            if not can_manage:
                st.info("운영자 권한에서는 설정 조회만 가능합니다.")
            st.caption("프로덕션에서는 HTTPS + AUTH_COOKIE_SECURE=1 설정을 권장합니다.")


# ============================================================
# STEP 7: Split View (핵심 UI)
# ============================================================

def render_split_view():
    """
    ChatPDF 스타일 Split View.

    왼쪽: 챗봇 대화 (질문 + 답변 + 참조 뱃지)
    오른쪽: PDF 뷰어 (하이라이트 어노테이션 + 자동 스크롤)

    왜 50:50 비율인가:
    ─────────────────
    ChatPDF, Adobe Acrobat AI, LightPDF 모두 약 50:50 비율 사용.
    사용자가 답변을 읽으면서 동시에 원문을 확인할 수 있는 최적 비율.
    모바일에서는 탭 전환 방식이 낫지만 데스크탑에서는 나란히가 효율적.
    """
    chat_col, pdf_col = st.columns([5, 5], gap="medium")

    # ── 왼쪽: 챗봇 ──
    with chat_col:
        render_chat_panel()

    # ── 오른쪽: PDF 뷰어 ──
    with pdf_col:
        render_pdf_viewer_panel()


def render_full_chat_view():
    """PDF 미업로드 시 전체 화면 챗봇"""
    st.info("💡 사이드바(☰)에서 분석할 문서를 업로드하면 **PDF 뷰어 + 하이라이트** 기능이 활성화됩니다!")

    tab1, tab2, tab3 = st.tabs(["💬 챗봇", "📊 분석 결과", "📋 문서 요약"])
    with tab1:
        render_chat_panel()
    with tab2:
        render_analysis_tab()
    with tab3:
        render_rfx_summary_tab()


# ============================================================
# STEP 8: 챗봇 패널
# ============================================================

def render_chat_panel():
    """챗봇 대화 패널"""

    def render_question_grid(questions: list[str], key_prefix: str, title: str) -> None:
        if not questions:
            return
        st.caption(title)
        normalized = [q.strip() for q in questions if q and q.strip()]
        for row_start in range(0, len(normalized), 2):
            row_cols = st.columns(2)
            for col_idx in range(2):
                q_idx = row_start + col_idx
                if q_idx >= len(normalized):
                    continue
                question = normalized[q_idx]
                with row_cols[col_idx]:
                    if st.button(
                        question,
                        key=f"{key_prefix}_{q_idx}",
                        use_container_width=True,
                    ):
                        process_chat_with_highlights(question)
                        st.rerun()

    def build_quick_questions() -> list[str]:
        if not st.session_state.company_docs_loaded and not st.session_state.rfx_loaded:
            return [
                "먼저 어떤 회사 문서를 올리면 분석 정확도가 좋아지나요?",
                "분석할 문서는 어떤 형식(PDF/DOCX/TXT)까지 가능한가요?",
                "로그인 후 문서가 F5 이후에도 유지되나요?",
                "처음 사용자를 위한 분석 순서를 알려주세요.",
            ]
        if st.session_state.company_docs_loaded and not st.session_state.rfx_loaded:
            return [
                "이제 어떤 문서를 올리면 바로 비교 분석할 수 있나요?",
                "문서 길이가 길어도 분석 가능하도록 팁을 알려주세요.",
                "문서 업로드 후 결과가 나오기까지 보통 얼마나 걸리나요?",
                "분석 전에 필수로 확인해야 할 항목 3가지만 알려주세요.",
            ]
        return [
            "미충족 항목 3개와 보완 우선순위를 알려줘.",
            "마감 전 제출서류 체크리스트를 일정 순서로 만들어줘.",
            "가장 리스크가 큰 항목과 대응안을 짧게 정리해줘.",
            "평가점수 개선에 가장 효과적인 준비 3가지를 알려줘.",
        ]

    # 대화 기록 표시
    for msg_idx, msg in enumerate(st.session_state.chat_history):
        with st.chat_message(msg["role"]):
            content = msg["content"]

            # 참조 뱃지를 클릭 가능한 HTML로 변환
            # [📄 p.3 "텍스트"] → `📄 p.3`
            # 보안: 모델 출력은 HTML 렌더링 금지(unsafe_allow_html=False 기본값 사용)
            import re
            content = re.sub(
                r'\[📄\s*p\.(\d+)(?:\s*"[^"]*")?\]',
                r'`📄 p.\1`',
                content
            )

            st.markdown(content)

            # 답변별 참조 이동 버튼
            references = msg.get("references", []) if msg["role"] == "assistant" else []
            if references:
                st.caption("참조 페이지 이동")
                max_refs = min(len(references), 5)
                ref_cols = st.columns(max_refs)
                for ref_idx, ref in enumerate(references[:max_refs]):
                    page = ref.get("page")
                    if not page:
                        continue
                    button_label = f"📄 p.{page}"
                    with ref_cols[ref_idx]:
                        if st.button(button_label, key=f"ref_jump_{msg_idx}_{ref_idx}", use_container_width=True):
                            st.session_state.scroll_to_page = page
                            st.session_state.scroll_to_annotation = None
                            st.rerun()

            suggested_questions = msg.get("suggested_questions", []) if msg["role"] == "assistant" else []
            if suggested_questions:
                render_question_grid(
                    questions=suggested_questions[:4],
                    key_prefix=f"suggested_q_{msg_idx}",
                    title="추천 질문",
                )

    # 빠른 질문 (첫 대화 시)
    if not st.session_state.chat_history:
        st.markdown("##### 💡 이런 질문을 해보세요:")
        render_question_grid(
            questions=build_quick_questions(),
            key_prefix="quick",
            title="빠른 시작 질문",
        )

    # 사용자 입력
    if user_input := st.chat_input("문서 분석 관련 질문을 입력하세요..."):
        process_chat_with_highlights(user_input)
        st.rerun()


# ============================================================
# STEP 9: PDF 뷰어 패널 (하이라이트 + 자동 스크롤)
#
# 📌 핵심 구현:
#    streamlit-pdf-viewer의 annotations, scroll_to_page,
#    scroll_to_annotation 파라미터를 활용.
#
#    - annotations: PyMuPDF로 찾은 좌표를 노란색 반투명 박스로 오버레이
#    - scroll_to_page: 첫 번째 하이라이트가 있는 페이지로 자동 이동
#    - scroll_to_annotation: 특정 어노테이션으로 직접 스크롤
# ============================================================

def render_pdf_viewer_panel():
    """
    PDF 뷰어 + 하이라이트 어노테이션.

    streamlit-pdf-viewer를 선택한 이유:
    ──────────────────────────────────
    1. PDF.js 기반 → 브라우저 네이티브 렌더링, 텍스트 선택/복사 가능
    2. annotations 파라미터 → 좌표 기반 오버레이 (형광펜 효과)
    3. scroll_to_page → 특정 페이지로 자동 스크롤
    4. scroll_to_annotation → 특정 어노테이션으로 스크롤
    5. 텍스트 레이어 지원 → render_text=True로 원문 텍스트 위에 렌더링
    6. Streamlit 세션 상태와 연동 → 챗봇 응답마다 동적 업데이트

    대안 비교:
    - iframe + base64: 어노테이션 불가, 스크롤 제어 제한적
    - PyMuPDF → 이미지: 스크롤 불가, 텍스트 선택 불가
    - react-pdf-highlighter: Streamlit에 통합 어려움
    """
    st.markdown(f"**📄 {st.session_state.pdf_filename}**")

    if st.session_state.pdf_viewer_required and not st.session_state.pdf_viewer_available:
        st.error(st.session_state.pdf_viewer_error)
        st.caption("운영 환경 의존성 복구 후 다시 시도해주세요.")
        return

    # 하이라이트 안내
    if st.session_state.current_annotations:
        n = len(st.session_state.current_annotations)
        st.markdown(
            f'<div class="highlight-info">'
            f'🔍 <strong>{n}개 참조</strong>가 노란색으로 하이라이트 되어 있습니다.'
            f'</div>',
            unsafe_allow_html=True
        )

    # 페이지 네비게이션 (수동)
    if st.session_state.highlight_manager:
        total_pages = st.session_state.highlight_manager.page_count
        if total_pages > 0:
            nav_col1, nav_col2 = st.columns([3, 1])
            with nav_col2:
                manual_page = st.number_input(
                    "페이지 이동",
                    min_value=1,
                    max_value=total_pages,
                    value=st.session_state.scroll_to_page or 1,
                    key="page_nav"
                )
                if manual_page != st.session_state.scroll_to_page:
                    st.session_state.scroll_to_page = manual_page
                    st.session_state.scroll_to_annotation = None

    # ── PDF 뷰어 렌더링 ──
    try:
        from streamlit_pdf_viewer import pdf_viewer

        viewer_kwargs = {
            "input": st.session_state.pdf_bytes,
            "width": "100%",
            "height": 680,
            "render_text": True,  # 텍스트 레이어 활성화
        }

        # 어노테이션 (하이라이트)
        if st.session_state.current_annotations:
            viewer_kwargs["annotations"] = st.session_state.current_annotations

        # 자동 스크롤
        if st.session_state.scroll_to_annotation:
            viewer_kwargs["scroll_to_annotation"] = st.session_state.scroll_to_annotation
        elif st.session_state.scroll_to_page:
            viewer_kwargs["scroll_to_page"] = st.session_state.scroll_to_page

        pdf_viewer(**viewer_kwargs)

    except ImportError:
        # 선택 모드에서만 폴백 허용
        if st.session_state.pdf_viewer_required:
            st.error(st.session_state.pdf_viewer_error)
            return
        st.warning("📦 `streamlit-pdf-viewer` 미설치. 기본 뷰어로 표시합니다.")
        render_pdf_fallback()

    except Exception as e:
        st.error(f"PDF 뷰어 오류: {e}")
        render_pdf_fallback()


def render_pdf_fallback():
    """
    streamlit-pdf-viewer 미설치 시 폴백.
    base64 iframe으로 PDF 표시 + PyMuPDF 이미지 하이라이트.

    왜 폴백이 필요한가:
    ─────────────────
    streamlit-pdf-viewer가 설치 안 된 환경에서도
    최소한의 PDF 표시 + 하이라이트 기능을 제공하기 위함.
    PyMuPDF로 해당 페이지를 이미지로 렌더링하고
    하이라이트 영역을 직접 그려서 표시.
    """
    import base64

    if st.session_state.pdf_bytes:
        # 하이라이트가 있으면 PyMuPDF로 이미지 렌더링
        if st.session_state.current_annotations and st.session_state.scroll_to_page:
            try:
                import fitz
                doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                page_idx = (st.session_state.scroll_to_page or 1) - 1
                page = doc[page_idx]

                # 하이라이트 사각형 추가
                for ann in st.session_state.current_annotations:
                    if ann["page"] == st.session_state.scroll_to_page:
                        rect = fitz.Rect(
                            ann["x"], ann["y"],
                            ann["x"] + ann["width"],
                            ann["y"] + ann["height"]
                        )
                        highlight = page.add_highlight_annot(rect)
                        highlight.set_colors(stroke=[1, 1, 0])  # 노란색
                        highlight.update()

                # 이미지로 렌더링
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                doc.close()

                st.image(img_bytes, use_container_width=True,
                         caption=f"📄 페이지 {st.session_state.scroll_to_page}")

            except Exception:
                # 최종 폴백: base64 iframe
                b64 = base64.b64encode(st.session_state.pdf_bytes).decode()
                page = st.session_state.scroll_to_page or 1
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{b64}#page={page}" '
                    f'width="100%" height="680" type="application/pdf"></iframe>',
                    unsafe_allow_html=True
                )
        else:
            # 하이라이트 없으면 기본 iframe
            b64 = base64.b64encode(st.session_state.pdf_bytes).decode()
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64}" '
                f'width="100%" height="680" type="application/pdf"></iframe>',
                unsafe_allow_html=True
            )


# ============================================================
# STEP 10: 분석 결과 탭 (기존 유지)
# ============================================================

OPINION_MODE_LABELS: dict[str, str] = {
    "conservative": "🛡️ 보수적",
    "balanced": "⚖️ 균형",
    "aggressive": "🚀 공격적",
}

OPINION_MODE_TONE_HINTS: dict[str, str] = {
    "conservative": "보수적: 리스크와 선확인 항목을 우선 제시합니다.",
    "balanced": "균형: 기회/리스크를 함께 보고 바로 실행할 수 있는 액션을 제안합니다.",
    "aggressive": "공격적: 참여 기회를 최대화하되 필수 리스크를 함께 고지합니다.",
}

BALANCED_VARIANT_LABELS: dict[str, str] = {
    "a": "A안(결론 우선형)",
    "b": "B안(리스크 관리형)",
}


def _normalize_opinion_mode(mode: str) -> str:
    alias = {
        "보수적": "conservative",
        "conservative": "conservative",
        "균형": "balanced",
        "balanced": "balanced",
        "공격적": "aggressive",
        "aggressive": "aggressive",
    }
    return alias.get(str(mode or "").strip().lower(), "balanced")


def _normalize_balanced_variant(variant: str) -> str:
    normalized = str(variant or "").strip().lower()
    if normalized in {"a", "결론", "결론우선", "결론우선형"}:
        return "a"
    if normalized in {"b", "리스크", "리스크관리", "리스크관리형"}:
        return "b"
    return "a"


def _opinion_cache_key(mode: str, balanced_variant: str | None = None) -> str:
    normalized_mode = _normalize_opinion_mode(mode)
    if normalized_mode != "balanced":
        return normalized_mode
    if not balanced_variant:
        return "balanced"
    return f"balanced_{_normalize_balanced_variant(balanced_variant)}"


def get_or_generate_opinion_for_mode(
    result,
    rfx,
    mode: str,
    balanced_variant: str | None = None,
) -> dict:
    """
    Kira 의견 캐시 조회 후 필요 시 1회 생성한다.
    생성 실패 시 빈 페이로드를 반환한다.
    """
    normalized_mode = _normalize_opinion_mode(mode)
    cache_key = _opinion_cache_key(normalized_mode, balanced_variant)
    cached = result.assistant_opinions.get(cache_key, {})
    if isinstance(cached, dict) and (
        str(cached.get("opinion", "")).strip()
        or cached.get("actions")
        or cached.get("risk_notes")
    ):
        log_opinion_experiment(
            event="cache_hit",
            mode=normalized_mode,
            variant=(balanced_variant or ""),
            extra={"cache_key": cache_key},
        )
        return cached

    api_key = str(st.session_state.api_key or "").strip()
    if not api_key:
        log_opinion_experiment(
            event="generation_skipped_no_api_key",
            mode=normalized_mode,
            variant=(balanced_variant or ""),
            extra={"cache_key": cache_key},
        )
        return {"opinion": "", "actions": [], "risk_notes": []}

    try:
        from matcher import QualificationMatcher

        matcher = QualificationMatcher(
            rag_engine=st.session_state.company_rag_engine,
            api_key=api_key,
        )
        payload = matcher.generate_opinion_for_mode(
            result=result,
            rfx=rfx,
            mode=normalized_mode,
            balanced_variant=balanced_variant,
        )
        if isinstance(payload, dict):
            log_opinion_experiment(
                event="generated",
                mode=normalized_mode,
                variant=(balanced_variant or ""),
                extra={"cache_key": cache_key},
            )
            return payload
    except Exception:
        log_opinion_experiment(
            event="generation_error",
            mode=normalized_mode,
            variant=(balanced_variant or ""),
            extra={"cache_key": cache_key},
        )
        pass
    return {"opinion": "", "actions": [], "risk_notes": []}


def render_analysis_tab():
    """자격 매칭 분석 결과"""
    if not st.session_state.matching_result:
        st.info("📌 분석할 문서를 업로드하고 분석하면 결과가 표시됩니다.")
        return

    result = st.session_state.matching_result
    rfx = st.session_state.rfx_analysis

    st.markdown("### 📊 종합 분석 결과")
    st.caption("`종합 적합도`는 자격 충족 기반 점수, `평가예상점수`는 기술/가격/가점 배점 기반 추정치입니다.")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("종합 적합도", f"{result.overall_score:.0f}%")
    with col2:
        st.metric("✅ 충족", f"{result.met_count}개")
    with col3:
        st.metric("🟡 부분충족", f"{result.partially_met_count}개")
    with col4:
        st.metric("❌ 미충족", f"{result.not_met_count}개")
    with col5:
        if result.evaluation_available and result.evaluation_total_score > 0:
            st.metric(
                "평가예상점수",
                f"{result.evaluation_expected_score:.1f}/{result.evaluation_total_score:.1f}"
            )
        else:
            st.metric("평가예상점수", "N/A")

    st.markdown(f"**추천:** {result.recommendation}")
    if result.evaluation_available:
        st.markdown(
            f"**기술/가격/가점 예상:** "
            f"{result.technical_expected_score:.1f} / {result.price_expected_score:.1f} / {result.bonus_expected_score:.1f}"
        )
        for note in result.evaluation_notes:
            st.caption(f"- {note}")
    st.divider()

    st.markdown("### 📝 자격요건별 분석")
    for match in result.matches:
        status_emoji = {"충족": "✅", "부분충족": "🟡", "미충족": "❌", "판단불가": "❓"}.get(match.status.value, "?")
        mandatory = "🔴 필수" if match.requirement.is_mandatory else "🟢 권장"
        with st.expander(f"{status_emoji} [{mandatory}] {match.requirement.description}",
                         expanded=(match.status.value in ["미충족", "부분충족"])):
            st.markdown(f"**상태:** {match.status.value} (신뢰도: {match.confidence:.0%})")
            if match.evidence:
                st.markdown(f"**근거:** {match.evidence}")
            if match.preparation_guide:
                st.warning(f"📌 준비사항: {match.preparation_guide}")

    if result.gaps:
        st.divider()
        st.markdown("### 🔍 GAP 분석")
        for gap in result.gaps:
            st.markdown(f"- **{gap.requirement.description}**")
            if gap.preparation_guide:
                st.markdown(f"  → {gap.preparation_guide}")

    st.divider()
    st.markdown("### 🧾 사실 기반 요약")
    st.markdown(result.summary)

    st.divider()
    st.markdown("### 💡 Kira 의견")

    mode_keys = ["conservative", "balanced", "aggressive"]
    current_mode = _normalize_opinion_mode(st.session_state.analysis_opinion_mode)
    if current_mode not in mode_keys:
        current_mode = "balanced"
    selected_label = st.radio(
        "판단 강도",
        options=[OPINION_MODE_LABELS[key] for key in mode_keys],
        index=mode_keys.index(current_mode),
        horizontal=True,
        key="analysis_opinion_mode_selector",
    )
    label_to_mode = {label: key for key, label in OPINION_MODE_LABELS.items()}
    selected_mode = label_to_mode.get(selected_label, "balanced")
    st.session_state.analysis_opinion_mode = selected_mode
    if st.session_state.analysis_last_logged_mode != selected_mode:
        log_opinion_experiment(event="mode_selected", mode=selected_mode)
        st.session_state.analysis_last_logged_mode = selected_mode
    st.caption(OPINION_MODE_TONE_HINTS.get(selected_mode, ""))

    opinion_payload = result.assistant_opinions.get(_opinion_cache_key(selected_mode), {})
    if not opinion_payload:
        with st.spinner("Kira 의견 생성 중..."):
            opinion_payload = get_or_generate_opinion_for_mode(result, rfx, selected_mode)
            result.assistant_opinions[_opinion_cache_key(selected_mode)] = opinion_payload
            result.opinion_mode = selected_mode
            st.session_state.matching_result = result

    opinion_text = str(opinion_payload.get("opinion", "")).strip()
    actions = [str(item).strip() for item in opinion_payload.get("actions", []) if str(item).strip()][:4]
    risk_notes = [str(item).strip() for item in opinion_payload.get("risk_notes", []) if str(item).strip()][:2]

    if opinion_text:
        st.markdown(opinion_text)
    else:
        st.info("의견 생성에 실패했습니다. 사실 기반 요약을 우선 참고해주세요.")

    if actions:
        st.markdown("#### 📋 다음 할 일")
        for action in actions:
            st.markdown(f"- [ ] {action}")

    if risk_notes:
        st.markdown("#### ⚠️ 주의할 점")
        for note in risk_notes:
            st.markdown(f"- {note}")

    if _get_env_bool("KIRA_OPINION_AB_ENABLED", True):
        st.divider()
        with st.expander("🧪 균형형 프롬프트 A/B 비교 실험", expanded=False):
            st.caption(
                "A안은 결론/액션 중심, B안은 리스크 관리 중심으로 생성됩니다. "
                "첫 생성 이후에는 캐시를 재사용합니다."
            )
            col_gen_a, col_gen_b = st.columns(2)
            with col_gen_a:
                if st.button("A안 생성/갱신", key="btn_generate_balanced_a", use_container_width=True):
                    with st.spinner("A안 생성 중..."):
                        payload_a = get_or_generate_opinion_for_mode(
                            result=result,
                            rfx=rfx,
                            mode="balanced",
                            balanced_variant="a",
                        )
                        result.assistant_opinions[_opinion_cache_key("balanced", "a")] = payload_a
                        st.session_state.matching_result = result
                        log_opinion_experiment(
                            event="balanced_variant_selected",
                            mode="balanced",
                            variant="a",
                        )
            with col_gen_b:
                if st.button("B안 생성/갱신", key="btn_generate_balanced_b", use_container_width=True):
                    with st.spinner("B안 생성 중..."):
                        payload_b = get_or_generate_opinion_for_mode(
                            result=result,
                            rfx=rfx,
                            mode="balanced",
                            balanced_variant="b",
                        )
                        result.assistant_opinions[_opinion_cache_key("balanced", "b")] = payload_b
                        st.session_state.matching_result = result
                        log_opinion_experiment(
                            event="balanced_variant_selected",
                            mode="balanced",
                            variant="b",
                        )

            col_a, col_b = st.columns(2)
            for variant, column in (("a", col_a), ("b", col_b)):
                payload = result.assistant_opinions.get(_opinion_cache_key("balanced", variant), {})
                with column:
                    st.markdown(f"**{BALANCED_VARIANT_LABELS[variant]}**")
                    text = str(payload.get("opinion", "")).strip()
                    todo_items = [
                        str(item).strip()
                        for item in payload.get("actions", [])
                        if str(item).strip()
                    ][:4]
                    if text:
                        st.markdown(text)
                    else:
                        st.caption("아직 생성되지 않았습니다.")
                    if todo_items:
                        for item in todo_items:
                            st.markdown(f"- [ ] {item}")

    st.caption("⚠️ Kira의 의견은 AI 참고용이며, 최종 판단은 담당자께서 해주세요.")

    report_text = result.to_report()
    st.download_button("📥 리포트 다운로드", data=report_text,
                       file_name="rfx_report.txt", mime="text/plain")


# ============================================================
# STEP 11: RFx 요약 탭 (기존 유지)
# ============================================================

def render_rfx_summary_tab():
    """분석 문서 요약"""
    if not st.session_state.rfx_analysis:
        st.info("📌 분석할 문서를 업로드하면 요약이 표시됩니다.")
        return

    rfx = st.session_state.rfx_analysis

    st.markdown("### 📋 문서 기본 정보")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**공고명:** {rfx.title}")
        st.markdown(f"**발주기관:** {rfx.issuing_org}")
    with col2:
        st.markdown(f"**마감일:** {rfx.deadline}")
        st.markdown(f"**예산:** {rfx.budget}")

    st.divider()
    st.markdown("### ✅ 자격요건")
    for req in rfx.requirements:
        mandatory = "🔴 필수" if req.is_mandatory else "🟢 권장"
        st.markdown(f"- [{mandatory}] **{req.category}**: {req.description}")

    if rfx.required_documents:
        st.divider()
        st.markdown("### 📎 제출서류")
        for doc in rfx.required_documents:
            st.markdown(f"- ☐ {doc}")

    rfx_json = json.dumps(rfx.to_dict(), ensure_ascii=False, indent=2)
    st.download_button("📥 JSON 다운로드", data=rfx_json,
                       file_name="rfx_analysis.json", mime="application/json")


# ============================================================
# STEP 12: 실행
# ============================================================

render_sidebar()
render_main()
