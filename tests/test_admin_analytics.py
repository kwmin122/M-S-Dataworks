from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import user_store as us


def _setup_temp_store(tmp_path: Path, monkeypatch) -> None:
    base_dir = tmp_path / "user_store_test"
    monkeypatch.setattr(us, "BASE_DIR", base_dir)
    monkeypatch.setattr(us, "DB_PATH", base_dir / "user_store.db")
    monkeypatch.setattr(us, "UPLOAD_ROOT", base_dir / "uploads")
    us.init_user_store()


def test_admin_overview_counts(tmp_path: Path, monkeypatch) -> None:
    _setup_temp_store(tmp_path, monkeypatch)

    ok1, _ = us.create_user("admin", "password123")
    ok2, _ = us.create_user("alice", "password123")
    assert ok1 and ok2

    us.touch_last_login("admin")
    _ = us.create_user_session("admin", ttl_days=7)
    _ = us.create_user_session("alice", ttl_days=7)

    us.save_company_file("admin", "company_profile.txt", b"hello")
    us.save_company_file("alice", "cert.pdf", b"%PDF-1.4")

    overview = us.get_admin_overview(days=7)
    assert overview["total_users"] == 2
    assert overview["total_sessions"] == 2
    assert overview["active_sessions"] == 2
    assert overview["total_files"] == 2
    assert overview["upload_users"] == 2
    assert overview["recent_uploads_window"] == 2


def test_user_activity_and_recent_files(tmp_path: Path, monkeypatch) -> None:
    _setup_temp_store(tmp_path, monkeypatch)
    ok, _ = us.create_user("bob", "password123")
    assert ok
    us.touch_last_login("bob")
    us.save_company_file("bob", "a.txt", b"A")
    us.save_company_file("bob", "b.txt", b"BBBB")

    activity = us.list_user_activity(limit=10)
    assert activity
    assert activity[0]["username"] == "bob"
    assert activity[0]["file_count"] >= 2

    recent_files = us.list_recent_company_files(limit=10)
    assert len(recent_files) == 2
    assert recent_files[0]["username"] == "bob"
    assert "size_bytes" in recent_files[0]
