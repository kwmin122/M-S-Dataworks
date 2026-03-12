"""
로컬 로그인/세션/회사 문서 영속 저장 유틸리티.

목적:
1) F5(새 세션) 이후에도 로그인 상태 복원
2) 사용자별 회사 문서 파일 저장 및 목록 복원
3) 사용자별 분리된 저장소 경로 제공
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Any


BASE_DIR = Path("./data/user_store")
DB_PATH = BASE_DIR / "user_store.db"
UPLOAD_ROOT = BASE_DIR / "uploads"
USAGE_ACTION_CHAT = "chat"
USAGE_ACTION_ANALYZE = "analyze"
VALID_USAGE_ACTIONS = {USAGE_ACTION_CHAT, USAGE_ACTION_ANALYZE}


@dataclass
class StoredFile:
    id: int
    username: str
    original_name: str
    stored_path: str
    file_ext: str
    uploaded_at: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_slug(value: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "_" for ch in (value or "").strip().lower())
    normalized = normalized.strip("_")
    return normalized[:48] or "user"


def username_to_scope(username: str) -> str:
    return _to_slug(username)


@contextmanager
def _connect():
    """Yield a sqlite3 connection that is properly closed on exit."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_user_store() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                token_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(username) REFERENCES users(username)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS company_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_ext TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                UNIQUE(username, stored_path),
                FOREIGN KEY(username) REFERENCES users(username)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS social_identities (
                provider TEXT NOT NULL,
                external_sub TEXT NOT NULL,
                username TEXT NOT NULL,
                email TEXT,
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL,
                PRIMARY KEY(provider, external_sub),
                FOREIGN KEY(username) REFERENCES users(username)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_key TEXT NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_usage_actor_action_created
            ON usage_events(actor_key, action, created_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_usage_username_created
            ON usage_events(username, created_at)
            """
        )
        conn.commit()


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return digest.hex()


def create_user(username: str, password: str) -> tuple[bool, str]:
    username = (username or "").strip()
    if len(username) < 3:
        return (False, "아이디는 3자 이상이어야 합니다.")
    if len(password or "") < 8:
        return (False, "비밀번호는 8자 이상이어야 합니다.")

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    created_at = _utc_now().isoformat()

    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, salt, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, password_hash, salt, created_at),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return (False, "이미 존재하는 아이디입니다.")

    return (True, "회원가입이 완료되었습니다.")


def _ensure_unique_username(base_username: str) -> str:
    base = _to_slug(base_username)[:32] or "user"
    candidate = base
    suffix = 1
    with _connect() as conn:
        while True:
            exists = conn.execute(
                "SELECT 1 FROM users WHERE username = ?",
                (candidate,),
            ).fetchone()
            if not exists:
                return candidate
            suffix += 1
            candidate = f"{base}_{suffix}"


def upsert_social_user(
    provider: str,
    external_sub: str,
    email: str = "",
    display_name: str = "",
) -> str:
    """
    소셜 로그인 사용자를 users/social_identities에 upsert하고 username을 반환한다.
    """
    provider_norm = (provider or "").strip().lower()
    external_sub_norm = (external_sub or "").strip()
    email_norm = (email or "").strip().lower()
    display_norm = (display_name or "").strip()
    if not provider_norm or not external_sub_norm:
        raise ValueError("provider and external_sub are required")

    now_iso = _utc_now().isoformat()
    with _connect() as conn:
        existing = conn.execute(
            """
            SELECT username FROM social_identities
            WHERE provider = ? AND external_sub = ?
            """,
            (provider_norm, external_sub_norm),
        ).fetchone()
        if existing:
            username = str(existing["username"])
            conn.execute(
                """
                UPDATE social_identities
                SET email = ?, last_login_at = ?
                WHERE provider = ? AND external_sub = ?
                """,
                (email_norm, now_iso, provider_norm, external_sub_norm),
            )
            conn.execute(
                "UPDATE users SET last_login_at = ? WHERE username = ?",
                (now_iso, username),
            )
            conn.commit()
            return username

        if email_norm:
            preferred = email_norm.split("@", 1)[0]
        elif display_norm:
            preferred = display_norm
        else:
            preferred = f"{provider_norm}_{external_sub_norm[:10]}"

        username = _ensure_unique_username(preferred)
        salt = secrets.token_hex(16)
        # 소셜 전용 계정의 패스워드 필드는 로그인 미사용 placeholder
        password_hash = _hash_password(secrets.token_urlsafe(24), salt)

        conn.execute(
            """
            INSERT INTO users (username, password_hash, salt, created_at, last_login_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, password_hash, salt, now_iso, now_iso),
        )
        conn.execute(
            """
            INSERT INTO social_identities (provider, external_sub, username, email, created_at, last_login_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (provider_norm, external_sub_norm, username, email_norm, now_iso, now_iso),
        )
        conn.commit()
    return username


def verify_user(username: str, password: str) -> bool:
    username = (username or "").strip()
    with _connect() as conn:
        row = conn.execute(
            "SELECT password_hash, salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return False

    candidate = _hash_password(password or "", row["salt"])
    return secrets.compare_digest(candidate, row["password_hash"])


def touch_last_login(username: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE username = ?",
            (_utc_now().isoformat(), username),
        )
        conn.commit()


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user_session(username: str, ttl_days: int = 7) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_session_token(token)
    now = _utc_now()
    expires_at = (now + timedelta(days=ttl_days)).isoformat()

    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO user_sessions (token_hash, username, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (token_hash, username, expires_at, now.isoformat()),
        )
        conn.commit()
    return token


def resolve_user_from_session(token: str) -> Optional[str]:
    if not token:
        return None
    token_hash = _hash_session_token(token)
    with _connect() as conn:
        row = conn.execute(
            "SELECT username, expires_at FROM user_sessions WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
    if not row:
        return None

    try:
        expires_at = datetime.fromisoformat(row["expires_at"])
    except ValueError:
        return None

    if expires_at <= _utc_now():
        invalidate_user_session(token)
        return None
    return str(row["username"])


def invalidate_user_session(token: str) -> None:
    if not token:
        return
    token_hash = _hash_session_token(token)
    with _connect() as conn:
        conn.execute(
            "DELETE FROM user_sessions WHERE token_hash = ?",
            (token_hash,),
        )
        conn.commit()


def _safe_filename(name: str) -> str:
    keep = []
    for ch in (name or "document"):
        if ch.isalnum() or ch in ("-", "_", ".", " "):
            keep.append(ch)
        else:
            keep.append("_")
    cleaned = "".join(keep).strip().replace(" ", "_")
    return cleaned[:120] or "document"


def save_company_file(username: str, original_name: str, content: bytes) -> StoredFile:
    username = (username or "").strip()
    if not username:
        raise ValueError("username is required")
    if not content:
        raise ValueError("empty file content")

    user_dir = UPLOAD_ROOT / username_to_scope(username)
    user_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(original_name)
    ext = Path(safe_name).suffix.lower() or ".bin"
    stored_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(6)}_{safe_name}"
    stored_path = user_dir / stored_name
    stored_path.write_bytes(content)

    uploaded_at = _utc_now().isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO company_files (username, original_name, stored_path, file_ext, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, original_name, str(stored_path), ext, uploaded_at),
        )
        conn.commit()
        file_id = int(cursor.lastrowid)

    return StoredFile(
        id=file_id,
        username=username,
        original_name=original_name,
        stored_path=str(stored_path),
        file_ext=ext,
        uploaded_at=uploaded_at,
    )


def list_company_files(username: str) -> list[StoredFile]:
    username = (username or "").strip()
    if not username:
        return []
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, username, original_name, stored_path, file_ext, uploaded_at
            FROM company_files
            WHERE username = ?
            ORDER BY uploaded_at DESC
            """,
            (username,),
        ).fetchall()

    files: list[StoredFile] = []
    for row in rows:
        files.append(
            StoredFile(
                id=int(row["id"]),
                username=str(row["username"]),
                original_name=str(row["original_name"]),
                stored_path=str(row["stored_path"]),
                file_ext=str(row["file_ext"]),
                uploaded_at=str(row["uploaded_at"]),
            )
        )
    return files


def count_company_files(username: str) -> int:
    username = (username or "").strip()
    if not username:
        return 0
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM company_files WHERE username = ?",
            (username,),
        ).fetchone()
    return int(row["c"] or 0)


def delete_company_files(username: str) -> dict[str, int]:
    """
    사용자 회사 문서를 DB/파일시스템에서 모두 삭제한다.
    """
    username = (username or "").strip()
    if not username:
        return {"db_deleted": 0, "file_deleted": 0, "file_missing": 0, "errors": 0}

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, stored_path
            FROM company_files
            WHERE username = ?
            """,
            (username,),
        ).fetchall()

        file_deleted = 0
        file_missing = 0
        errors = 0
        for row in rows:
            path = str(row["stored_path"] or "")
            if not path:
                file_missing += 1
                continue
            try:
                if os.path.exists(path):
                    os.remove(path)
                    file_deleted += 1
                else:
                    file_missing += 1
            except OSError:
                errors += 1

        deleted = conn.execute(
            "DELETE FROM company_files WHERE username = ?",
            (username,),
        ).rowcount
        conn.commit()

    return {
        "db_deleted": int(deleted or 0),
        "file_deleted": int(file_deleted),
        "file_missing": int(file_missing),
        "errors": int(errors),
    }


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _start_of_day(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_month(value: datetime) -> datetime:
    utc = value.astimezone(timezone.utc)
    return utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _normalize_usage_action(action: str) -> str:
    normalized = str(action or "").strip().lower()
    if normalized not in VALID_USAGE_ACTIONS:
        raise ValueError(f"unsupported usage action: {action}")
    return normalized


def record_usage_event(
    actor_key: str,
    username: str,
    action: str,
    metadata: Optional[dict[str, Any]] = None,
    created_at: Optional[datetime] = None,
) -> None:
    """사용량 이벤트를 1건 기록한다."""
    actor_norm = str(actor_key or "").strip()
    if not actor_norm:
        raise ValueError("actor_key is required")

    action_norm = _normalize_usage_action(action)
    username_norm = str(username or "").strip()
    created = (created_at or _utc_now()).astimezone(timezone.utc).isoformat()
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_events (actor_key, username, action, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (actor_norm, username_norm, action_norm, created, metadata_json),
        )
        conn.commit()


def get_actor_usage_counts(
    actor_key: str,
    action: str,
    now: Optional[datetime] = None,
) -> dict[str, int]:
    """특정 actor/action의 오늘/이번달 사용량 조회."""
    actor_norm = str(actor_key or "").strip()
    if not actor_norm:
        return {"today": 0, "month": 0}
    action_norm = _normalize_usage_action(action)
    current = (now or _utc_now()).astimezone(timezone.utc)
    day_start = _start_of_day(current).isoformat()
    month_start = _start_of_month(current).isoformat()

    with _connect() as conn:
        today_row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM usage_events
            WHERE actor_key = ? AND action = ? AND created_at >= ?
            """,
            (actor_norm, action_norm, day_start),
        ).fetchone()
        month_row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM usage_events
            WHERE actor_key = ? AND action = ? AND created_at >= ?
            """,
            (actor_norm, action_norm, month_start),
        ).fetchone()

    return {
        "today": int((today_row["c"] if today_row else 0) or 0),
        "month": int((month_row["c"] if month_row else 0) or 0),
    }


def enforce_usage_quota(
    *,
    actor_key: str,
    username: str,
    action: str,
    daily_limit: int = 0,
    monthly_limit: int = 0,
    metadata: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    사용량 제한을 검사하고 허용 시 이벤트를 기록한다.

    Args:
        actor_key: 사용자/익명 세션 식별자
        username: 로그인 사용자명(없으면 빈 문자열)
        action: chat 또는 analyze
        daily_limit: 0 이하면 일일 제한 비활성
        monthly_limit: 0 이하면 월간 제한 비활성
    """
    action_norm = _normalize_usage_action(action)
    current = (now or _utc_now()).astimezone(timezone.utc)
    counts = get_actor_usage_counts(actor_key=actor_key, action=action_norm, now=current)

    daily_limit_norm = max(0, int(daily_limit or 0))
    monthly_limit_norm = max(0, int(monthly_limit or 0))

    if daily_limit_norm > 0 and counts["today"] >= daily_limit_norm:
        return {
            "allowed": False,
            "action": action_norm,
            "reason": "DAILY_LIMIT_EXCEEDED",
            "today_used": counts["today"],
            "today_limit": daily_limit_norm,
            "month_used": counts["month"],
            "month_limit": monthly_limit_norm,
        }

    if monthly_limit_norm > 0 and counts["month"] >= monthly_limit_norm:
        return {
            "allowed": False,
            "action": action_norm,
            "reason": "MONTHLY_LIMIT_EXCEEDED",
            "today_used": counts["today"],
            "today_limit": daily_limit_norm,
            "month_used": counts["month"],
            "month_limit": monthly_limit_norm,
        }

    record_usage_event(
        actor_key=actor_key,
        username=username,
        action=action_norm,
        metadata=metadata,
        created_at=current,
    )
    return {
        "allowed": True,
        "action": action_norm,
        "reason": "",
        "today_used": counts["today"] + 1,
        "today_limit": daily_limit_norm,
        "month_used": counts["month"] + 1,
        "month_limit": monthly_limit_norm,
    }


def get_usage_overview(now: Optional[datetime] = None) -> dict[str, int]:
    """오늘/이번달 사용량 총계를 반환한다."""
    current = (now or _utc_now()).astimezone(timezone.utc)
    day_start = _start_of_day(current).isoformat()
    month_start = _start_of_month(current).isoformat()

    with _connect() as conn:
        today_rows = conn.execute(
            """
            SELECT action, COUNT(*) AS c
            FROM usage_events
            WHERE created_at >= ?
            GROUP BY action
            """,
            (day_start,),
        ).fetchall()
        month_rows = conn.execute(
            """
            SELECT action, COUNT(*) AS c
            FROM usage_events
            WHERE created_at >= ?
            GROUP BY action
            """,
            (month_start,),
        ).fetchall()
        active_today_row = conn.execute(
            """
            SELECT COUNT(DISTINCT actor_key) AS c
            FROM usage_events
            WHERE created_at >= ?
            """,
            (day_start,),
        ).fetchone()
        active_month_row = conn.execute(
            """
            SELECT COUNT(DISTINCT actor_key) AS c
            FROM usage_events
            WHERE created_at >= ?
            """,
            (month_start,),
        ).fetchone()

    today_counts = {str(row["action"]): int(row["c"] or 0) for row in today_rows}
    month_counts = {str(row["action"]): int(row["c"] or 0) for row in month_rows}
    return {
        "today_chat": int(today_counts.get(USAGE_ACTION_CHAT, 0)),
        "today_analyze": int(today_counts.get(USAGE_ACTION_ANALYZE, 0)),
        "month_chat": int(month_counts.get(USAGE_ACTION_CHAT, 0)),
        "month_analyze": int(month_counts.get(USAGE_ACTION_ANALYZE, 0)),
        "active_actors_today": int((active_today_row["c"] if active_today_row else 0) or 0),
        "active_actors_month": int((active_month_row["c"] if active_month_row else 0) or 0),
    }


def list_usage_by_actor(limit: int = 200, now: Optional[datetime] = None) -> list[dict[str, Any]]:
    """사용자/세션별 오늘/이번달 사용량."""
    current = (now or _utc_now()).astimezone(timezone.utc)
    day_start = _start_of_day(current).isoformat()
    month_start = _start_of_month(current).isoformat()

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                actor_key,
                MAX(username) AS username,
                SUM(CASE WHEN action = 'chat' AND created_at >= ? THEN 1 ELSE 0 END) AS today_chat,
                SUM(CASE WHEN action = 'analyze' AND created_at >= ? THEN 1 ELSE 0 END) AS today_analyze,
                SUM(CASE WHEN action = 'chat' AND created_at >= ? THEN 1 ELSE 0 END) AS month_chat,
                SUM(CASE WHEN action = 'analyze' AND created_at >= ? THEN 1 ELSE 0 END) AS month_analyze,
                MAX(created_at) AS last_event_at
            FROM usage_events
            GROUP BY actor_key
            ORDER BY last_event_at DESC
            LIMIT ?
            """,
            (day_start, day_start, month_start, month_start, max(1, int(limit))),
        ).fetchall()

    return [
        {
            "actor_key": str(row["actor_key"] or ""),
            "username": str(row["username"] or ""),
            "today_chat": int(row["today_chat"] or 0),
            "today_analyze": int(row["today_analyze"] or 0),
            "month_chat": int(row["month_chat"] or 0),
            "month_analyze": int(row["month_analyze"] or 0),
            "last_event_at": str(row["last_event_at"] or ""),
        }
        for row in rows
    ]


def get_admin_overview(days: int = 7) -> dict[str, int]:
    """
    관리자 대시보드용 핵심 집계.
    """
    now = _utc_now()
    since = now - timedelta(days=max(1, int(days)))

    with _connect() as conn:
        total_users = int(conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"])
        total_sessions = int(conn.execute("SELECT COUNT(*) AS c FROM user_sessions").fetchone()["c"])
        total_files = int(conn.execute("SELECT COUNT(*) AS c FROM company_files").fetchone()["c"])
        upload_user_count = int(
            conn.execute("SELECT COUNT(DISTINCT username) AS c FROM company_files").fetchone()["c"]
        )

        session_rows = conn.execute("SELECT expires_at FROM user_sessions").fetchall()
        active_sessions = 0
        for row in session_rows:
            expires_at = _parse_iso_datetime(str(row["expires_at"] or ""))
            if expires_at and expires_at > now:
                active_sessions += 1

        user_rows = conn.execute("SELECT last_login_at FROM users").fetchall()
        active_users = 0
        for row in user_rows:
            last_login = _parse_iso_datetime(str(row["last_login_at"] or ""))
            if last_login and last_login >= since:
                active_users += 1

        file_rows = conn.execute("SELECT uploaded_at FROM company_files").fetchall()
        recent_uploads = 0
        for row in file_rows:
            uploaded_at = _parse_iso_datetime(str(row["uploaded_at"] or ""))
            if uploaded_at and uploaded_at >= since:
                recent_uploads += 1

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "total_files": total_files,
        "upload_users": upload_user_count,
        "active_users_window": active_users,
        "recent_uploads_window": recent_uploads,
        "window_days": max(1, int(days)),
    }


def list_user_activity(limit: int = 50) -> list[dict[str, Any]]:
    """
    사용자별 최근 활동 요약 목록.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                u.username AS username,
                u.created_at AS created_at,
                u.last_login_at AS last_login_at,
                COUNT(cf.id) AS file_count
            FROM users u
            LEFT JOIN company_files cf ON cf.username = u.username
            GROUP BY u.username, u.created_at, u.last_login_at
            ORDER BY COALESCE(u.last_login_at, u.created_at) DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()

    return [
        {
            "username": str(row["username"]),
            "created_at": str(row["created_at"] or ""),
            "last_login_at": str(row["last_login_at"] or ""),
            "file_count": int(row["file_count"] or 0),
        }
        for row in rows
    ]


def list_recent_company_files(limit: int = 50) -> list[dict[str, Any]]:
    """
    최근 업로드 문서 목록(관리자용).
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT username, original_name, file_ext, uploaded_at, stored_path
            FROM company_files
            ORDER BY uploaded_at DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        stored_path = str(row["stored_path"] or "")
        file_size = 0
        try:
            if stored_path and os.path.exists(stored_path):
                file_size = int(os.path.getsize(stored_path))
        except OSError:
            file_size = 0
        items.append(
            {
                "username": str(row["username"] or ""),
                "original_name": str(row["original_name"] or ""),
                "file_ext": str(row["file_ext"] or ""),
                "uploaded_at": str(row["uploaded_at"] or ""),
                "size_bytes": file_size,
            }
        )
    return items


def get_user_profile(username: str) -> dict[str, str]:
    """
    사용자 프로필(이메일/소셜 제공자 포함) 조회.
    """
    username_norm = (username or "").strip()
    if not username_norm:
        return {}

    with _connect() as conn:
        user_row = conn.execute(
            """
            SELECT username, created_at, last_login_at
            FROM users
            WHERE username = ?
            """,
            (username_norm,),
        ).fetchone()
        if not user_row:
            return {}

        social_row = conn.execute(
            """
            SELECT provider, email
            FROM social_identities
            WHERE username = ?
            ORDER BY last_login_at DESC
            LIMIT 1
            """,
            (username_norm,),
        ).fetchone()

    return {
        "username": str(user_row["username"] or ""),
        "email": str((social_row["email"] if social_row else "") or ""),
        "provider": str((social_row["provider"] if social_row else "") or ""),
        "created_at": str(user_row["created_at"] or ""),
        "last_login_at": str(user_row["last_login_at"] or ""),
    }
