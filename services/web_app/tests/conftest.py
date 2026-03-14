from __future__ import annotations

import asyncio
import os
import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

from services.web_app.db.models import Base


# --- PostgreSQL REQUIRED ---
# No SQLite fallback. JSONB, BigInteger autoincrement, CHECK constraints,
# partial unique indexes, deferrable FKs, pgvector all require PostgreSQL.
# SQLite cannot even compile JSONB type → "Compiler can't render element of type JSONB".
#
# docker-compose.yml provides: postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test

_TEST_DB_URL = os.getenv("BID_TEST_DATABASE_URL", "")
_DB_AVAILABLE = bool(_TEST_DB_URL and "postgresql" in _TEST_DB_URL)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def _pg_engine():
    """Session-scoped engine. Creates schema once with pgvector extension."""
    if not _DB_AVAILABLE:
        pytest.skip(
            "BID_TEST_DATABASE_URL not set or not PostgreSQL. "
            "Run: docker compose up kira_bid_test_db -d && "
            "export BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test'"
        )
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(_pg_engine):
    """Per-test async session with transactional isolation.

    Outer connection-level transaction wraps entire test.
    Session.commit() creates/releases savepoints within the outer txn.
    After test, outer txn rolls back → zero side effects.
    """
    # --- Outer connection transaction pattern ---
    # 1. Open raw connection, begin outer transaction (never committed)
    async with _pg_engine.connect() as conn:
        txn = await conn.begin()

        # 2. Bind session to this connection
        # Session.commit() → savepoint release, NOT real commit
        session = AsyncSession(bind=conn, expire_on_commit=False)

        # 3. Start first savepoint (session.commit() will release + re-create)
        nested = await conn.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(session_sync, transaction):
            """After session.commit() releases savepoint, start a new one."""
            if transaction.nested and not transaction._parent.nested:
                # inner savepoint ended, restart
                conn_sync = conn.sync_connection
                if conn_sync is not None:
                    conn_sync.begin_nested()

        yield session

        # 4. Cleanup: close session, rollback outer txn
        await session.close()
        await txn.rollback()
