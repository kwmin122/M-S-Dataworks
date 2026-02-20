from pathlib import Path
import sys

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

APP_PATH = str(PROJECT_ROOT / "app.py")


def _expander_labels(at: AppTest) -> list[str]:
    return [exp.label for exp in at.expander if hasattr(exp, "label")]


def _radio_labels(at: AppTest) -> list[str]:
    return [radio.label for radio in at.radio if hasattr(radio, "label")]


def _tab_labels(at: AppTest) -> list[str]:
    return [tab.label for tab in at.tabs if hasattr(tab, "label")]


def test_admin_dashboard_visible_for_super_admin_user(monkeypatch) -> None:
    monkeypatch.setenv("SUPER_ADMIN_USERNAMES", "admin")
    monkeypatch.setenv("OPERATOR_USERNAMES", "operator")
    at = AppTest.from_file(APP_PATH)
    at.session_state["is_authenticated"] = True
    at.session_state["auth_username"] = "admin"
    at.session_state["api_key"] = ""
    at.run(timeout=30)

    labels = _expander_labels(at)
    assert "🛠 관리자 대시보드" in labels
    assert "KPI 기간" in _radio_labels(at)
    assert "🚨 알림" in _tab_labels(at)


def test_admin_dashboard_hidden_for_non_admin_user() -> None:
    at = AppTest.from_file(APP_PATH)
    at.session_state["is_authenticated"] = True
    at.session_state["auth_username"] = "alice"
    at.session_state["api_key"] = ""
    at.run(timeout=30)

    labels = _expander_labels(at)
    assert "🛠 관리자 대시보드" not in labels


def test_admin_dashboard_visible_for_operator_user(monkeypatch) -> None:
    monkeypatch.setenv("SUPER_ADMIN_USERNAMES", "admin")
    monkeypatch.setenv("OPERATOR_USERNAMES", "ops")
    at = AppTest.from_file(APP_PATH)
    at.session_state["is_authenticated"] = True
    at.session_state["auth_username"] = "ops"
    at.session_state["api_key"] = ""
    at.run(timeout=30)

    labels = _expander_labels(at)
    assert "🛠 관리자 대시보드" in labels
