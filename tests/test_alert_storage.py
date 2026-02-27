import json
import hashlib
from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.web_app.alert_storage import (
    get_alert_config,
    save_alert_config,
    get_alert_config_path,
)

@pytest.fixture
def cleanup_test_alerts():
    """Clean up test alert files after test"""
    yield
    test_dir = Path("data/user_alerts")
    if test_dir.exists():
        for f in test_dir.glob("*.json"):
            if "test" in f.read_text():
                f.unlink()

def test_save_and_load_alert_config(cleanup_test_alerts):
    """Save alert config and retrieve it"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9, 18],
        "rules": [{
            "id": "1",
            "keywords": ["교통신호등"],
            "enabled": True,
        }],
    }

    # Save
    save_alert_config(config)

    # Load
    loaded = get_alert_config("test@example.com")

    assert loaded["email"] == "test@example.com"
    assert loaded["schedule"] == "daily_2"
    assert len(loaded["rules"]) == 1
    assert "createdAt" in loaded
    assert "updatedAt" in loaded

def test_get_nonexistent_config_returns_default():
    """Get config for email that doesn't exist returns default"""
    config = get_alert_config("nonexistent@example.com")

    assert config["email"] == "nonexistent@example.com"
    assert config["enabled"] is False
    assert config["schedule"] == "daily_1"
    assert config["rules"] == []

def test_email_hash_consistent():
    """Email hash should be consistent (lowercase normalized)"""
    path1 = get_alert_config_path("User@Example.COM")
    path2 = get_alert_config_path("user@example.com")

    assert path1 == path2

def test_get_alert_config_rejects_invalid_email():
    """get_alert_config should raise ValueError for invalid email"""
    with pytest.raises(ValueError, match="유효한 이메일"):
        get_alert_config("invalid-email")

    with pytest.raises(ValueError, match="유효한 이메일"):
        get_alert_config("")

    with pytest.raises(ValueError, match="유효한 이메일"):
        get_alert_config(None)

def test_save_alert_config_rejects_invalid_email():
    """save_alert_config should raise ValueError for invalid email"""
    config = {"email": "invalid-email", "rules": []}

    with pytest.raises(ValueError, match="유효한 이메일"):
        save_alert_config(config)

    config["email"] = ""
    with pytest.raises(ValueError, match="유효한 이메일"):
        save_alert_config(config)
