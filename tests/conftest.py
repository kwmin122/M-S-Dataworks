"""Shared test fixtures for root tests/.

Handles two sources of 429 in test:
1. slowapi rate limiter — in-memory, reset per test
2. usage quota system — disabled via QUOTA_ENABLED=0
"""

import os
import pytest

# Disable usage quota system for all tests.
# _quota_enabled() in web_app/main.py checks this env var and skips quota
# enforcement when it's falsy. Without this, the SQLite-backed quota counter
# accumulates across test runs and eventually triggers 429.
os.environ["QUOTA_ENABLED"] = "0"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset slowapi rate limiter state before each test.

    The web_app uses a module-level in-memory rate limiter (slowapi).
    Without resetting, tests sharing the global TestClient accumulate
    request counts and later tests hit 429 spuriously.
    """
    from services.web_app.main import limiter

    try:
        storage = limiter._limiter.storage
        storage.reset()
    except Exception:
        pass  # If storage API changes, don't break tests
    yield
