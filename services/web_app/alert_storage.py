import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

_ROOT_DIR = Path(__file__).resolve().parents[2]
ALERTS_DIR = _ROOT_DIR / "data" / "user_alerts"

def get_alert_config_path(email: str) -> Path:
    """Get file path for alert config (email normalized to lowercase)"""
    email_hash = hashlib.sha256(email.lower().strip().encode()).hexdigest()
    return ALERTS_DIR / f"{email_hash}.json"

def get_alert_config(email: str) -> dict[str, Any]:
    """Load alert config for email, return default if not exists"""
    if not email or '@' not in email:
        raise ValueError("유효한 이메일 주소가 필요합니다.")

    file_path = get_alert_config_path(email)

    if not file_path.exists():
        return _default_alert_config(email)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # Corrupted file or I/O error - return default config (graceful degradation)
        print(f"⚠️ Failed to load alert config for {email}: {e}")
        return _default_alert_config(email)

def save_alert_config(config: dict[str, Any]) -> None:
    """Save alert config to file"""
    email = config.get("email")
    if not email or '@' not in email:
        raise ValueError("유효한 이메일 주소가 필요합니다.")

    # Add/update timestamps
    now = datetime.now(timezone.utc).isoformat()
    config["updatedAt"] = now
    if "createdAt" not in config:
        config["createdAt"] = now

    # Ensure directory exists
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)

    # Write to file
    file_path = get_alert_config_path(email)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except OSError as e:
        raise IOError(f"알림 설정 저장 실패: {e}") from e

def _default_alert_config(email: str) -> dict[str, Any]:
    """Return default config for new user"""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "email": email,
        "enabled": False,
        "schedule": "daily_1",
        "hours": [9],
        "rules": [],
        "createdAt": now,
        "updatedAt": now,
    }
