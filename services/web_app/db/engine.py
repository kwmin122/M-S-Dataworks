from __future__ import annotations

import os
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_database_url() -> str:
    url = os.getenv("BID_DATABASE_URL", "")
    if not url:
        raise RuntimeError("BID_DATABASE_URL environment variable is required")
    if "postgresql" not in url:
        raise RuntimeError(
            f"BID_DATABASE_URL must be PostgreSQL (got: {url[:20]}...). "
            "SQLite is NOT supported — JSONB, CHECK constraints, pgvector require PostgreSQL."
        )
    return url


async def init_db() -> None:
    global _engine, _async_session_factory
    if _engine is not None:
        return
    _engine = create_async_engine(
        _get_database_url(),
        echo=os.getenv("BID_DB_ECHO", "").lower() == "true",
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    _async_session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )


async def close_db() -> None:
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


async def get_async_session() -> AsyncSession:
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _async_session_factory() as session:
        yield session


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global async session factory for manual session creation.

    Used by write-through paths that need to create their own async context
    outside of FastAPI dependency injection.

    Raises:
        RuntimeError: If database not initialized (call init_db() first)
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session_factory
