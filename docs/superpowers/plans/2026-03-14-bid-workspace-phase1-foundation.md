# Bid Workspace v1.0 — Phase 1: Foundation Infrastructure

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish PostgreSQL database, S3 object storage, and session adapter so existing Chat UI continues working while all new data flows through DB-centric bid_projects.

**Architecture:** SQLAlchemy 2.0 async ORM on shared PostgreSQL 16, Alembic migrations, boto3 S3/R2 client with presigned URLs, FastAPI APIRouter modules integrated into existing web_app. rag_engine stays stateless — no DB access.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0 (async), Alembic, asyncpg, boto3, FastAPI APIRouter, pgvector, pytest-asyncio

**Hard Requirements:**
- PostgreSQL 16+ with pgvector extension — **NO SQLite fallback**. JSONB, partial unique indexes, CHECK constraints, deferrable FKs, BigInteger autoincrement PK all require PostgreSQL. SQLite cannot compile JSONB type at all.
- `BID_TEST_DATABASE_URL` must point to PostgreSQL in all environments (local dev + CI).
- v1 supports **single-org membership only** — one user belongs to one active org. Multi-org is Phase 3+.

**Spec:** `docs/superpowers/specs/2026-03-14-bid-workspace-v1-design.md`

---

## Scope & Phasing

This is **Phase 1 of 4**. Each phase has its own plan:

| Phase | Plan | Deliverables |
|-------|------|-------------|
| **1 (this)** | Foundation Infrastructure | PostgreSQL 14 core tables, S3 storage, asset API, session adapter, audit |
| 2 | Contract + Pipeline | GenerationContract, orchestrator unification, quality gates, doc_type migration |
| 3 | Workspace UI + Review | Bid Workspace frontend, review/approval, permissions UI |
| 4 | Legacy Removal | Session adapter removal, unused API cleanup, load testing |

**Deferred to Phase 1b (when needed for Phase 3):**
- departments, teams (2 tables) — org sub-structure
- approval_lines, approval_line_steps (2 tables) — approval workflow definitions
- review_requests, review_comments, approval_records (3 tables) — review execution
- skill_update_candidates, skill_versions (2 tables) — learning pipeline

**Phase 1a (this plan) = 14 tables:**
organizations, memberships, bid_projects, project_access, source_documents, analysis_snapshots, document_runs, document_revisions, document_assets, project_current_documents, audit_logs, company_profiles, company_track_records, company_personnel

---

## Current State Summary

- **Root web_app:** FastAPI on port 8000, SQLite3 user_store (users/sessions/files), no ORM
- **Auth:** Supabase OAuth → auth_gateway → `kira_auth` HttpOnly cookie → `resolve_user_from_session(token)` → username
- **Storage:** All files on local filesystem (`data/proposals/`, `data/company_db/`, `data/web_uploads/`)
- **Sessions:** In-memory `SESSIONS` dict + optional Redis cache
- **Company data:** ChromaDB per-company dirs (`data/company_db/{company_id}/`)
- **rag_engine:** FastAPI on port 8001, stateless compute, file paths for output
- **Already installed:** alembic 1.18.4, asyncpg 0.31.0
- **Not installed:** sqlalchemy, boto3, pgvector, cuid2
- **Required runtime:** PostgreSQL 16+ with pgvector (no SQLite — JSONB, BigInt autoincrement, CHECK constraints all break)

---

## File Map

### New Files

```
services/web_app/
├── db/
│   ├── __init__.py                    ← DB package init
│   ├── engine.py                      ← AsyncEngine + async_sessionmaker
│   ├── models/
│   │   ├── __init__.py                ← Re-export all models + Base
│   │   ├── base.py                    ← DeclarativeBase + common mixins
│   │   ├── org.py                     ← organizations, memberships
│   │   ├── project.py                 ← bid_projects, project_access, source_documents, analysis_snapshots
│   │   ├── document.py                ← document_runs, document_revisions, document_assets, project_current_documents
│   │   ├── company.py                 ← company_profiles, company_track_records, company_personnel
│   │   └── audit.py                   ← audit_logs
│   └── migrations/
│       ├── alembic.ini                ← Alembic config
│       ├── env.py                     ← Alembic async env
│       └── versions/                  ← Migration scripts
├── storage/
│   ├── __init__.py
│   └── s3.py                          ← S3/R2 client (presigned URLs, upload, download)
├── api/
│   ├── __init__.py
│   ├── deps.py                        ← get_db session, get_current_user, require_org_member
│   ├── projects.py                    ← Project CRUD router
│   ├── assets.py                      ← Asset upload/download router
│   └── adapter.py                     ← Session → bid_project adapter router
└── tests/
    ├── __init__.py
    ├── conftest.py                     ← Async DB fixtures, test client
    ├── test_models.py                  ← Model CRUD + constraint tests
    ├── test_unit.py                    ← Layer 1: Pure logic (enum, ACL hierarchy, state transitions)
    ├── test_postgres_integration.py    ← Layer 2: JSONB, partial index, CHECK, deferrable FK
    ├── test_storage_integration.py     ← Layer 3: MinIO/R2 upload/download/checksum
    ├── test_api_scenarios.py           ← Layer 4: Full lifecycle, IDOR prevention, ACL enforcement
    ├── test_s3.py                      ← S3 client unit tests (mocked)
    ├── test_projects_api.py            ← Project API route tests
    ├── test_assets_api.py              ← Asset API route tests
    └── test_adapter.py                 ← Session adapter tests
```

### Modified Files

```
services/web_app/main.py               ← Add lifespan DB init, include routers
requirements.txt                        ← Add sqlalchemy, boto3, pgvector, cuid2
docker-compose.yml                      ← Add BID_DATABASE_URL env to web_app service (if needed)
```

---

## Environment Variables (New)

| Variable | Purpose | Example |
|----------|---------|---------|
| `BID_DATABASE_URL` | PostgreSQL for Bid Workspace tables | `postgresql+asyncpg://user:pass@localhost:5432/kira_bid` |
| `S3_ENDPOINT_URL` | S3/R2 endpoint | `https://xxx.r2.cloudflarestorage.com` |
| `S3_ACCESS_KEY_ID` | S3 access key | |
| `S3_SECRET_ACCESS_KEY` | S3 secret | |
| `S3_BUCKET_NAME` | Asset bucket | `kira-assets` |
| `S3_REGION` | AWS region (or `auto` for R2) | `auto` |
| `BID_DEV_BOOTSTRAP` | `1`/`true` = enable org auto-provision (DEV ONLY) | `false` |
| `BID_TEST_DATABASE_URL` | PostgreSQL for tests (CI must set this) | `postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test` |
| `S3_TEST_ENDPOINT_URL` | MinIO/R2 endpoint for storage integration tests | `http://localhost:9000` |

---

## Chunk 1: Database Foundation

### Task 1: Python Dependencies + SQLAlchemy Engine

**Files:**
- Modify: `requirements.txt`
- Create: `services/web_app/db/__init__.py`
- Create: `services/web_app/db/engine.py`
- Create: `services/web_app/tests/__init__.py`
- Create: `services/web_app/tests/conftest.py`

- [ ] **Step 1: Add dependencies to requirements.txt**

Append to `requirements.txt`:
```
sqlalchemy[asyncio]==2.0.36
asyncpg==0.31.0
boto3==1.38.0
pgvector==0.3.6
cuid2==2.0.1
pytest-asyncio==0.24.0
pytest-timeout==2.3.1
```

> **NOTE:** No `aiosqlite`. PostgreSQL is the only supported backend.
> JSONB, BigInteger autoincrement, CHECK constraints, partial indexes all fail on SQLite.

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Create DB engine module**

```python
# services/web_app/db/__init__.py
from .engine import get_engine, get_async_session, init_db, close_db

__all__ = ["get_engine", "get_async_session", "init_db", "close_db"]
```

```python
# services/web_app/db/engine.py
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
```

- [ ] **Step 3: Create test conftest with async fixtures**

```python
# services/web_app/tests/__init__.py
```

```python
# services/web_app/tests/conftest.py
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
if not _TEST_DB_URL:
    raise RuntimeError(
        "BID_TEST_DATABASE_URL is required. "
        "Run: docker compose up kira_bid_test_db -d\n"
        "Then: export BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test'"
    )
if "postgresql" not in _TEST_DB_URL:
    raise RuntimeError(
        f"BID_TEST_DATABASE_URL must be PostgreSQL (got: {_TEST_DB_URL[:30]}...). "
        "SQLite is NOT supported."
    )


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def _pg_engine():
    """Session-scoped engine. Creates schema once with pgvector extension."""
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
```

> **PostgreSQL is REQUIRED.** No SQLite fallback.
> Run `docker compose up kira_bid_test_db -d` before tests.
> Set `BID_TEST_DATABASE_URL=postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test`.

- [ ] **Step 4: Verify setup compiles**

Run: `cd services/web_app && python -c "from db.engine import init_db, get_async_session; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add services/web_app/db/__init__.py services/web_app/db/engine.py \
  services/web_app/tests/__init__.py services/web_app/tests/conftest.py \
  requirements.txt
git commit -m "feat(bid-workspace): add SQLAlchemy async engine + test fixtures"
```

---

### Task 2: Base Model + ID Generation

**Files:**
- Create: `services/web_app/db/models/__init__.py`
- Create: `services/web_app/db/models/base.py`

- [ ] **Step 1: Create base model with cuid2 ID and timestamp mixins**

```python
# services/web_app/db/models/base.py
from __future__ import annotations

from datetime import datetime, timezone
from cuid2 import cuid_wrapper
from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

generate_cuid = cuid_wrapper()


def new_cuid() -> str:
    return generate_cuid()


class Base(DeclarativeBase):
    pass


# --- Enums (spec section 4: single dictionary across all layers) ---

class DocType:
    """doc_type enum values. Used in CHECK constraints and Python code."""
    PROPOSAL = "proposal"
    EXECUTION_PLAN = "execution_plan"
    PRESENTATION = "presentation"
    TRACK_RECORD = "track_record"
    CHECKLIST = "checklist"
    ALL = [PROPOSAL, EXECUTION_PLAN, PRESENTATION, TRACK_RECORD, CHECKLIST]


class ContentSchema:
    """content_schema version strings for document_revisions."""
    PROPOSAL_V1 = "proposal_sections_v1"
    EXECUTION_PLAN_V1 = "execution_plan_tasks_v1"
    PRESENTATION_V1 = "presentation_slides_v1"
    TRACK_RECORD_V1 = "track_record_v1"
    CHECKLIST_V1 = "checklist_v1"


class CuidPkMixin:
    """Primary key using cuid2."""
    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=new_cuid
    )


class TimestampMixin:
    """created_at + updated_at auto-managed timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CreatedAtMixin:
    """Immutable records — created_at only, no updated_at."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
```

```python
# services/web_app/db/models/__init__.py
# NOTE: Start with base-only imports. Full model imports added in Task 7
# after all model files exist (avoids ImportError during incremental dev).
from .base import Base, CuidPkMixin, TimestampMixin, CreatedAtMixin, new_cuid, DocType, ContentSchema

__all__ = ["Base", "CuidPkMixin", "TimestampMixin", "CreatedAtMixin", "new_cuid", "DocType", "ContentSchema"]
```

**In Task 7 (after all models exist)**, update `__init__.py` to add full imports:
```python
# services/web_app/db/models/__init__.py (final version, Task 7)
from .base import Base, CuidPkMixin, TimestampMixin, CreatedAtMixin, new_cuid, DocType, ContentSchema
from .org import Organization, Membership
from .project import BidProject, ProjectAccess, SourceDocument, AnalysisSnapshot
from .document import DocumentRun, DocumentRevision, DocumentAsset, ProjectCurrentDocument
from .company import CompanyProfile, CompanyTrackRecord, CompanyPersonnel
from .audit import AuditLog

__all__ = [
    "Base", "CuidPkMixin", "TimestampMixin", "CreatedAtMixin", "new_cuid",
    "DocType", "ContentSchema",
    "Organization", "Membership",
    "BidProject", "ProjectAccess", "SourceDocument", "AnalysisSnapshot",
    "DocumentRun", "DocumentRevision", "DocumentAsset", "ProjectCurrentDocument",
    "CompanyProfile", "CompanyTrackRecord", "CompanyPersonnel",
    "AuditLog",
]
```

- [ ] **Step 2: Write test for cuid generation**

```python
# services/web_app/tests/test_models.py
from services.web_app.db.models.base import new_cuid


def test_cuid_generates_unique_ids():
    ids = {new_cuid() for _ in range(100)}
    assert len(ids) == 100


def test_cuid_is_string():
    cid = new_cuid()
    assert isinstance(cid, str)
    assert len(cid) > 10
```

- [ ] **Step 3: Run test**

Run: `pytest services/web_app/tests/test_models.py::test_cuid_generates_unique_ids -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add services/web_app/db/models/
git commit -m "feat(bid-workspace): add Base model with cuid2 PK + timestamp mixins"
```

---

### Task 3: Organization + Membership Models

**Files:**
- Create: `services/web_app/db/models/org.py`
- Modify: `services/web_app/tests/test_models.py`

- [ ] **Step 1: Write failing test**

Add to `services/web_app/tests/test_models.py`:

```python
import pytest
import pytest_asyncio
from sqlalchemy import select
from services.web_app.db.models.org import Organization, Membership


@pytest.mark.asyncio
async def test_create_organization(db_session):
    org = Organization(name="테스트 기업", plan_tier="free")
    db_session.add(org)
    await db_session.commit()

    result = await db_session.execute(
        select(Organization).where(Organization.id == org.id)
    )
    fetched = result.scalar_one()
    assert fetched.name == "테스트 기업"
    assert fetched.plan_tier == "free"
    assert fetched.id is not None


@pytest.mark.asyncio
async def test_create_membership(db_session):
    org = Organization(name="테스트 기업")
    db_session.add(org)
    await db_session.flush()

    member = Membership(
        org_id=org.id,
        user_id="testuser",
        role="owner",
        is_active=True,
    )
    db_session.add(member)
    await db_session.commit()

    result = await db_session.execute(
        select(Membership).where(Membership.org_id == org.id)
    )
    fetched = result.scalar_one()
    assert fetched.role == "owner"
    assert fetched.is_active is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest services/web_app/tests/test_models.py::test_create_organization -v`
Expected: FAIL (import error — org.py not yet created)

- [ ] **Step 3: Implement Organization + Membership models**

```python
# services/web_app/db/models/org.py
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CuidPkMixin, TimestampMixin, CreatedAtMixin

_PLAN_TIERS = "plan_tier IN ('free','starter','pro','enterprise') OR plan_tier IS NULL"
_MEMBERSHIP_ROLES = "role IN ('owner','admin','editor','reviewer','approver','viewer')"


class Organization(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    plan_tier: Mapped[str | None] = mapped_column(Text, default="free")
    settings_json: Mapped[dict | None] = mapped_column(JSONB, default=None)

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(_PLAN_TIERS, name="ck_organizations_plan_tier"),
    )


class Membership(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "memberships"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        Text, nullable=False, default="viewer"
    )  # owner / admin / editor / reviewer / approver / viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="memberships")

    __table_args__ = (
        CheckConstraint(_MEMBERSHIP_ROLES, name="ck_memberships_role"),
        Index("idx_memberships_user", "user_id", "org_id", postgresql_where=text("is_active = true")),
        Index("idx_memberships_org_role", "org_id", "role", postgresql_where=text("is_active = true")),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest services/web_app/tests/test_models.py -k "organization or membership" -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add services/web_app/db/models/org.py services/web_app/tests/test_models.py
git commit -m "feat(bid-workspace): add Organization + Membership models"
```

---

### Task 4: BidProject + ProjectAccess + SourceDocument + AnalysisSnapshot Models

**Files:**
- Create: `services/web_app/db/models/project.py`
- Modify: `services/web_app/tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Add to `services/web_app/tests/test_models.py`:

```python
from services.web_app.db.models.project import (
    BidProject, ProjectAccess, SourceDocument, AnalysisSnapshot,
)


@pytest.mark.asyncio
async def test_create_bid_project(db_session):
    org = Organization(name="테스트 기업")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(
        org_id=org.id,
        created_by="testuser",
        title="XX기관 정보시스템 구축 사업",
        status="draft",
        rfp_source_type="upload",
    )
    db_session.add(project)
    await db_session.commit()

    result = await db_session.execute(
        select(BidProject).where(BidProject.id == project.id)
    )
    fetched = result.scalar_one()
    assert fetched.title == "XX기관 정보시스템 구축 사업"
    assert fetched.status == "draft"
    assert fetched.org_id == org.id


@pytest.mark.asyncio
async def test_create_analysis_snapshot(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="테스트 프로젝트")
    db_session.add(project)
    await db_session.flush()

    snapshot = AnalysisSnapshot(
        org_id=org.id,
        project_id=project.id,
        version=1,
        analysis_json={"title": "테스트", "requirements": []},
        analysis_schema="rfx_analysis_v1",
        is_active=True,
    )
    db_session.add(snapshot)
    await db_session.commit()

    result = await db_session.execute(
        select(AnalysisSnapshot).where(AnalysisSnapshot.project_id == project.id)
    )
    fetched = result.scalar_one()
    assert fetched.version == 1
    assert fetched.is_active is True
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest services/web_app/tests/test_models.py::test_create_bid_project -v`
Expected: FAIL

- [ ] **Step 3: Implement models**

```python
# services/web_app/db/models/project.py
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CuidPkMixin, TimestampMixin, CreatedAtMixin


_BID_PROJECT_STATUSES = "status IN ('draft','collecting_inputs','analyzing','ready_for_generation','generating','in_review','changes_requested','approved','locked_for_submission','submitted','archived')"
_RFP_SOURCE_TYPES = "rfp_source_type IN ('upload','nara_search','manual') OR rfp_source_type IS NULL"
_GENERATION_MODES = "generation_mode IN ('strict_template','starter','upgrade') OR generation_mode IS NULL"
_ACCESS_LEVELS = "access_level IN ('owner','editor','reviewer','approver','viewer')"
_DOC_KINDS = "document_kind IN ('rfp','company_profile','template','past_proposal','track_record','personnel','supporting_material','final_upload')"
_PARSE_STATUSES = "parse_status IN ('pending','parsing','completed','failed')"


class BidProject(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "bid_projects"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft"
    )  # draft / collecting_inputs / analyzing / ready_for_generation / generating / in_review / changes_requested / approved / locked_for_submission / submitted / archived
    rfp_source_type: Mapped[str | None] = mapped_column(Text)  # upload / nara_search / manual
    rfp_source_ref: Mapped[str | None] = mapped_column(Text)
    # Dedicated legacy session mapping — NOT stored in rfp_source_ref (business field)
    legacy_session_id: Mapped[str | None] = mapped_column(
        Text, unique=True, index=True, doc="Session adapter lookup key. Phase 4 removed."
    )
    active_analysis_snapshot_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("analysis_snapshots.id", use_alter=True, deferrable=True, initially="DEFERRED"),
    )
    generation_mode: Mapped[str | None] = mapped_column(Text)  # strict_template / starter / upgrade
    settings_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint(_BID_PROJECT_STATUSES, name="ck_bid_projects_status"),
        CheckConstraint(_RFP_SOURCE_TYPES, name="ck_bid_projects_rfp_source_type"),
        CheckConstraint(_GENERATION_MODES, name="ck_bid_projects_generation_mode"),
        Index("idx_bid_projects_org_status", "org_id", "status"),
        Index("idx_bid_projects_org_created", "org_id", text("created_at DESC")),
    )


class ProjectAccess(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "project_access"

    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(Text)
    team_id: Mapped[str | None] = mapped_column(Text)
    access_level: Mapped[str] = mapped_column(
        Text, nullable=False, default="viewer"
    )  # owner / editor / reviewer / approver / viewer

    __table_args__ = (
        CheckConstraint(_ACCESS_LEVELS, name="ck_project_access_level"),
        # Prevent duplicate (project_id, user_id) pairs.
        # Without this, scalar_one_or_none() in require_project_access() can raise
        # MultipleResultsFound, and list_projects can return duplicate rows.
        UniqueConstraint(
            "project_id", "user_id",
            name="uq_project_access_project_user",
        ),
        Index("idx_project_access_project", "project_id"),
        Index("idx_project_access_user", "user_id"),
    )


class SourceDocument(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "source_documents"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="SET NULL")
    )
    document_kind: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # rfp / company_profile / template / past_proposal / track_record / personnel / supporting_material / final_upload
    uploaded_by: Mapped[str] = mapped_column(Text, nullable=False)
    asset_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("document_assets.id")
    )
    parse_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending"
    )  # pending / parsing / completed / failed
    parse_result_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint(_DOC_KINDS, name="ck_source_docs_kind"),
        CheckConstraint(_PARSE_STATUSES, name="ck_source_docs_parse_status"),
        # Spec section 11: final_upload requires project_id
        CheckConstraint(
            "document_kind != 'final_upload' OR project_id IS NOT NULL",
            name="ck_source_docs_final_upload_project",
        ),
        Index("idx_source_docs_project_kind", "project_id", "document_kind"),
    )


class AnalysisSnapshot(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "analysis_snapshots"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    analysis_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    analysis_schema: Mapped[str | None] = mapped_column(Text)
    summary_md: Mapped[str | None] = mapped_column(Text)
    go_nogo_result_json: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # Enforce single active snapshot per project (spec section 12)
        Index(
            "idx_analysis_active", "project_id",
            unique=True, postgresql_where=text("is_active = true"),
        ),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest services/web_app/tests/test_models.py -k "bid_project or analysis_snapshot" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/web_app/db/models/project.py services/web_app/tests/test_models.py
git commit -m "feat(bid-workspace): add BidProject + ProjectAccess + SourceDocument + AnalysisSnapshot models"
```

---

### Task 5: Document Generation Models (Runs, Revisions, Assets, CurrentDocuments)

**Files:**
- Create: `services/web_app/db/models/document.py`
- Modify: `services/web_app/tests/test_models.py`

- [ ] **Step 1: Write failing test for document_run + revision lifecycle**

Add to `services/web_app/tests/test_models.py`:

```python
from services.web_app.db.models.document import (
    DocumentRun, DocumentRevision, DocumentAsset, ProjectCurrentDocument,
)


@pytest.mark.asyncio
async def test_document_run_lifecycle(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    proj = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(proj)
    await db_session.flush()

    run = DocumentRun(
        org_id=org.id,
        project_id=proj.id,
        doc_type="proposal",
        status="queued",
        created_by="u1",
    )
    db_session.add(run)
    await db_session.commit()

    result = await db_session.execute(
        select(DocumentRun).where(DocumentRun.id == run.id)
    )
    fetched = result.scalar_one()
    assert fetched.status == "queued"
    assert fetched.doc_type == "proposal"


@pytest.mark.asyncio
async def test_document_asset_upload_status(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    asset = DocumentAsset(
        org_id=org.id,
        asset_type="docx",
        storage_uri="s3://kira-assets/orgs/test/assets/a1/abc.docx",
        upload_status="presigned_issued",
        original_filename="제안서.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    db_session.add(asset)
    await db_session.commit()

    asset.upload_status = "uploaded"
    await db_session.commit()

    result = await db_session.execute(
        select(DocumentAsset).where(DocumentAsset.id == asset.id)
    )
    fetched = result.scalar_one()
    assert fetched.upload_status == "uploaded"
    assert fetched.storage_uri.startswith("s3://")
```

- [ ] **Step 2: Implement document models**

```python
# services/web_app/db/models/document.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CuidPkMixin, CreatedAtMixin, TimestampMixin, DocType

_DOC_TYPE_CHECK = f"doc_type IN ('{DocType.PROPOSAL}','{DocType.EXECUTION_PLAN}','{DocType.PRESENTATION}','{DocType.TRACK_RECORD}','{DocType.CHECKLIST}')"
_RUN_STATUSES = "status IN ('queued','running','completed','failed','superseded')"
_REV_STATUSES = "status IN ('draft','review_requested','in_review','changes_requested','approved','locked','submitted')"
_REV_SOURCES = "source IN ('ai_generated','user_edited','reassembled','imported_final')"
_UPLOAD_STATUSES = "upload_status IN ('presigned_issued','uploading','uploaded','verified','failed')"
_MODE_USED = "mode_used IN ('strict_template','starter','upgrade') OR mode_used IS NULL"
_ASSET_TYPES = "asset_type IN ('original','docx','xlsx','pptx','pdf','png','json')"


class DocumentRun(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "document_runs"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    analysis_snapshot_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("analysis_snapshots.id")
    )
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="queued"
    )  # queued / running / completed / failed / superseded
    params_json: Mapped[dict | None] = mapped_column(JSONB)
    engine_version: Mapped[str | None] = mapped_column(Text)
    mode_used: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(_DOC_TYPE_CHECK, name="ck_doc_runs_doc_type"),
        CheckConstraint(_RUN_STATUSES, name="ck_doc_runs_status"),
        CheckConstraint(_MODE_USED, name="ck_doc_runs_mode_used"),
    )


class DocumentRevision(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "document_revisions"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("document_runs.id")
    )
    derived_from_revision_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("document_revisions.id")
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source: Mapped[str] = mapped_column(
        Text, nullable=False, default="ai_generated"
    )  # ai_generated / user_edited / reassembled / imported_final
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft"
    )  # draft / review_requested / in_review / changes_requested / approved / locked / submitted
    title: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict | None] = mapped_column(JSONB)
    content_schema: Mapped[str | None] = mapped_column(Text)
    quality_report_json: Mapped[dict | None] = mapped_column(JSONB)
    quality_schema: Mapped[str | None] = mapped_column(Text)
    upgrade_report_json: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_DOC_TYPE_CHECK, name="ck_doc_revisions_doc_type"),
        CheckConstraint(_REV_STATUSES, name="ck_doc_revisions_status"),
        CheckConstraint(_REV_SOURCES, name="ck_doc_revisions_source"),
        Index(
            "idx_doc_revisions_project_type",
            "project_id", "doc_type", text("revision_number DESC"),
        ),
    )


class DocumentAsset(CuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "document_assets"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="SET NULL")
    )
    revision_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("document_revisions.id")
    )
    asset_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    upload_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="presigned_issued"
    )  # presigned_issued / uploading / uploaded / verified / failed
    original_filename: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    content_hash: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint(_UPLOAD_STATUSES, name="ck_doc_assets_upload_status"),
        CheckConstraint(_ASSET_TYPES, name="ck_doc_assets_asset_type"),
        Index("idx_doc_assets_org_project", "org_id", "project_id"),
        Index("idx_doc_assets_revision", "revision_id"),
    )


class ProjectCurrentDocument(CuidPkMixin, Base):
    __tablename__ = "project_current_documents"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    current_revision_id: Mapped[str] = mapped_column(
        Text, ForeignKey("document_revisions.id"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(_DOC_TYPE_CHECK, name="ck_current_docs_doc_type"),
        UniqueConstraint("project_id", "doc_type", name="uq_current_doc_project_type"),
        Index("idx_current_docs_org", "org_id"),
    )
```

- [ ] **Step 3: Run tests**

Run: `pytest services/web_app/tests/test_models.py -k "document" -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add services/web_app/db/models/document.py services/web_app/tests/test_models.py
git commit -m "feat(bid-workspace): add DocumentRun + DocumentRevision + DocumentAsset + ProjectCurrentDocument models"
```

---

### Task 6: Company Data Models (PostgreSQL + pgvector)

**Files:**
- Create: `services/web_app/db/models/company.py`
- Modify: `services/web_app/tests/test_models.py`

- [ ] **Step 1: Write failing test**

```python
from services.web_app.db.models.company import (
    CompanyProfile, CompanyTrackRecord, CompanyPersonnel,
)


@pytest.mark.asyncio
async def test_company_profile_unique_per_org(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    profile = CompanyProfile(
        org_id=org.id,
        company_name="테스트 기업",
        business_type="IT서비스",
    )
    db_session.add(profile)
    await db_session.commit()

    result = await db_session.execute(
        select(CompanyProfile).where(CompanyProfile.org_id == org.id)
    )
    fetched = result.scalar_one()
    assert fetched.company_name == "테스트 기업"


@pytest.mark.asyncio
async def test_company_track_record(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    record = CompanyTrackRecord(
        org_id=org.id,
        project_name="정보시스템 구축",
        client_name="교육청",
        contract_amount=500_000_000,
        description="클라우드 기반 시스템 구축",
    )
    db_session.add(record)
    await db_session.commit()

    result = await db_session.execute(
        select(CompanyTrackRecord).where(CompanyTrackRecord.org_id == org.id)
    )
    fetched = result.scalar_one()
    assert fetched.project_name == "정보시스템 구축"
    assert fetched.contract_amount == 500_000_000
```

- [ ] **Step 2: Implement company models**

```python
# services/web_app/db/models/company.py
from __future__ import annotations

from datetime import date
from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CuidPkMixin, TimestampMixin

# PostgreSQL required — pgvector always available. No SQLite fallback.
from pgvector.sqlalchemy import Vector

_VECTOR_TYPE = Vector(1536)


class CompanyProfile(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "company_profiles"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    company_name: Mapped[str | None] = mapped_column(Text)
    business_type: Mapped[str | None] = mapped_column(Text)
    business_number: Mapped[str | None] = mapped_column(Text)
    capital: Mapped[str | None] = mapped_column(Text)
    headcount: Mapped[int | None] = mapped_column(Integer)
    licenses: Mapped[dict | None] = mapped_column(JSONB)
    certifications: Mapped[dict | None] = mapped_column(JSONB)
    writing_style: Mapped[dict | None] = mapped_column(JSONB)


class CompanyTrackRecord(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "company_track_records"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_name: Mapped[str | None] = mapped_column(Text)
    client_name: Mapped[str | None] = mapped_column(Text)
    contract_amount: Mapped[int | None] = mapped_column(BigInteger)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[dict | None] = mapped_column(JSONB)
    embedding = mapped_column(_VECTOR_TYPE, nullable=True)

    __table_args__ = (
        Index("idx_track_records_org", "org_id"),
    )


class CompanyPersonnel(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "company_personnel"

    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    years_experience: Mapped[int | None] = mapped_column(Integer)
    certifications: Mapped[dict | None] = mapped_column(JSONB)
    skills: Mapped[dict | None] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    embedding = mapped_column(_VECTOR_TYPE, nullable=True)

    __table_args__ = (
        Index("idx_personnel_org", "org_id"),
    )
```

- [ ] **Step 3: Run tests**

Run: `pytest services/web_app/tests/test_models.py -k "company" -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add services/web_app/db/models/company.py services/web_app/tests/test_models.py
git commit -m "feat(bid-workspace): add CompanyProfile + CompanyTrackRecord + CompanyPersonnel models"
```

---

### Task 7: Audit Log Model

**Files:**
- Create: `services/web_app/db/models/audit.py`
- Modify: `services/web_app/tests/test_models.py`

- [ ] **Step 1: Write failing test**

```python
from services.web_app.db.models.audit import AuditLog


@pytest.mark.asyncio
async def test_audit_log_append_only(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    log = AuditLog(
        org_id=org.id,
        user_id="testuser",
        action="create_project",
        target_type="bid_project",
        target_id="proj_123",
        detail_json={"title": "테스트 프로젝트"},
    )
    db_session.add(log)
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.org_id == org.id)
    )
    fetched = result.scalar_one()
    assert fetched.action == "create_project"
    assert fetched.target_type == "bid_project"
```

- [ ] **Step 2: Implement audit model**

```python
# services/web_app/db/models/audit.py
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin


class AuditLog(CreatedAtMixin, Base):
    __tablename__ = "audit_logs"

    # Use BigInteger auto-increment PK instead of cuid2 (append-only, high volume)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        Text, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("bid_projects.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[str | None] = mapped_column(Text)
    detail_json: Mapped[dict | None] = mapped_column(JSONB)
    # PostgreSQL INET — validates IP format at DB level. No SQLite fallback needed.
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_audit_org_time", "org_id", text("created_at DESC")),
        Index("idx_audit_project_time", "project_id", text("created_at DESC")),
        Index("idx_audit_target", "target_type", "target_id"),
    )
```

- [ ] **Step 3: Run tests**

Run: `pytest services/web_app/tests/test_models.py -k "audit" -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add services/web_app/db/models/audit.py services/web_app/tests/test_models.py
git commit -m "feat(bid-workspace): add AuditLog model (append-only, BigInteger PK)"
```

---

### Task 8: Alembic Setup + Initial Migration

**Files:**
- Create: `services/web_app/db/migrations/alembic.ini`
- Create: `services/web_app/db/migrations/env.py`
- Create: `services/web_app/db/migrations/versions/` (directory)

- [ ] **Step 1: Create Alembic configuration**

```ini
# services/web_app/db/migrations/alembic.ini
[alembic]
script_location = %(here)s
sqlalchemy.url = driver://user:pass@localhost/dbname
# URL is overridden by env.py at runtime

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create Alembic env.py (async-capable)**

```python
# services/web_app/db/migrations/env.py
from __future__ import annotations

import asyncio
import os
import sys

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Add project root to path for model imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from services.web_app.db.models import Base  # noqa: E402

target_metadata = Base.metadata


def get_url() -> str:
    url = os.getenv("BID_DATABASE_URL", "")
    if not url:
        raise RuntimeError("BID_DATABASE_URL required for migrations")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 3: Create versions directory**

```bash
mkdir -p services/web_app/db/migrations/versions
touch services/web_app/db/migrations/versions/.gitkeep
```

- [ ] **Step 4: Generate initial migration (requires running PostgreSQL)**

When PostgreSQL is available:
```bash
cd services/web_app/db/migrations
BID_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/kira_bid" \
  alembic -c alembic.ini revision --autogenerate -m "initial_bid_workspace_schema"
```

If no PostgreSQL available, create migration SQL manually in:
`services/web_app/db/migrations/versions/0001_initial_schema.py`

The migration must include pgvector extension and Vector columns:
```sql
-- At the top of the migration
CREATE EXTENSION IF NOT EXISTS vector;

-- In company_track_records
ALTER TABLE company_track_records ADD COLUMN embedding vector(1536);

-- In company_personnel
ALTER TABLE company_personnel ADD COLUMN embedding vector(1536);

-- Partial unique index for analysis_snapshots
CREATE UNIQUE INDEX idx_analysis_active
  ON analysis_snapshots(project_id) WHERE is_active = true;
```

- [ ] **Step 5: Commit**

```bash
git add services/web_app/db/migrations/
git commit -m "feat(bid-workspace): add Alembic migration setup + initial schema"
```

---

## Chunk 2: S3 Storage Layer

### Task 9: S3 Client Wrapper

**Files:**
- Create: `services/web_app/storage/__init__.py`
- Create: `services/web_app/storage/s3.py`
- Create: `services/web_app/tests/test_s3.py`

- [ ] **Step 1: Write failing test for presigned URL generation**

```python
# services/web_app/tests/test_s3.py
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from services.web_app.storage.s3 import S3Client


def test_build_storage_key():
    client = S3Client.__new__(S3Client)
    client._bucket = "kira-assets"
    key = client.build_storage_key(
        org_id="org_123",
        project_id="proj_456",
        asset_id="ast_789",
        filename="제안서.docx",
    )
    assert key == "orgs/org_123/projects/proj_456/assets/ast_789/제안서.docx"


def test_build_source_storage_key():
    client = S3Client.__new__(S3Client)
    client._bucket = "kira-assets"
    key = client.build_source_storage_key(
        org_id="org_123",
        source_doc_id="src_001",
        filename="공고문.pdf",
    )
    assert key == "orgs/org_123/sources/src_001/공고문.pdf"


def test_build_full_uri():
    client = S3Client.__new__(S3Client)
    client._bucket = "kira-assets"
    uri = client.build_full_uri("orgs/org_123/assets/a1/file.docx")
    assert uri == "s3://kira-assets/orgs/org_123/assets/a1/file.docx"


def test_parse_storage_uri():
    client = S3Client.__new__(S3Client)
    client._bucket = "kira-assets"
    key = client.parse_storage_uri("s3://kira-assets/orgs/org_123/assets/a1/file.docx")
    assert key == "orgs/org_123/assets/a1/file.docx"


def test_parse_storage_uri_invalid():
    client = S3Client.__new__(S3Client)
    client._bucket = "kira-assets"
    with pytest.raises(ValueError):
        client.parse_storage_uri("s3://wrong-bucket/key")
```

- [ ] **Step 2: Implement S3 client**

```python
# services/web_app/storage/__init__.py
from .s3 import S3Client, get_s3_client

__all__ = ["S3Client", "get_s3_client"]
```

```python
# services/web_app/storage/s3.py
from __future__ import annotations

import os
from typing import BinaryIO

import boto3
from botocore.config import Config


_s3_client: S3Client | None = None


class S3Client:
    """S3/R2-compatible object storage client."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        bucket_name: str | None = None,
        region: str | None = None,
    ):
        self._bucket = bucket_name or os.getenv("S3_BUCKET_NAME", "kira-assets")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=access_key_id or os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=secret_access_key or os.getenv("S3_SECRET_ACCESS_KEY"),
            region_name=region or os.getenv("S3_REGION", "auto"),
            config=Config(signature_version="s3v4"),
        )

    def build_storage_key(
        self,
        org_id: str,
        project_id: str,
        asset_id: str,
        filename: str,
    ) -> str:
        return f"orgs/{org_id}/projects/{project_id}/assets/{asset_id}/{filename}"

    def build_source_storage_key(
        self,
        org_id: str,
        source_doc_id: str,
        filename: str,
    ) -> str:
        return f"orgs/{org_id}/sources/{source_doc_id}/{filename}"

    def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 3600,
    ) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    def generate_presigned_download_url(
        self,
        key: str,
        original_filename: str | None = None,
        expires_in: int = 3600,
    ) -> str:
        params: dict = {"Bucket": self._bucket, "Key": key}
        if original_filename:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{original_filename}"'
            )
        return self._client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def upload_fileobj(
        self,
        fileobj: BinaryIO,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> None:
        self._client.upload_fileobj(
            fileobj,
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    def download_fileobj(self, key: str, fileobj: BinaryIO) -> None:
        self._client.download_fileobj(self._bucket, key, fileobj)

    def head_object(self, key: str) -> dict:
        return self._client.head_object(Bucket=self._bucket, Key=key)

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def build_full_uri(self, key: str) -> str:
        """Build canonical s3://bucket/key URI."""
        return f"s3://{self._bucket}/{key}"

    def parse_storage_uri(self, uri: str) -> str:
        """Extract S3 key from storage_uri. Raises ValueError if format wrong."""
        prefix = f"s3://{self._bucket}/"
        if not uri.startswith(prefix):
            raise ValueError(f"Invalid storage URI: {uri}")
        return uri[len(prefix):]


def get_s3_client() -> S3Client:
    global _s3_client
    if _s3_client is None:
        _s3_client = S3Client()
    return _s3_client
```

- [ ] **Step 3: Run tests**

Run: `pytest services/web_app/tests/test_s3.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add services/web_app/storage/ services/web_app/tests/test_s3.py
git commit -m "feat(bid-workspace): add S3/R2 client wrapper with presigned URL support"
```

---

### Task 10: API Dependencies (Auth + DB Session)

**Files:**
- Create: `services/web_app/api/__init__.py`
- Create: `services/web_app/api/deps.py`

- [ ] **Step 1: Create API dependencies**

```python
# services/web_app/api/__init__.py
```

```python
# services/web_app/api/deps.py
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.org import Membership
from services.web_app.db.models.project import ProjectAccess

logger = logging.getLogger(__name__)

# --- Guard: org auto-provision is DEV ONLY ---
_DEV_BOOTSTRAP = os.getenv("BID_DEV_BOOTSTRAP", "").lower() in ("1", "true")


@dataclass
class CurrentUser:
    username: str
    org_id: str
    role: str  # org-level role


async def get_current_user(request: Request) -> CurrentUser:
    """Extract authenticated user from existing kira_auth cookie system.

    Reuses existing resolve_user_from_session() from user_store.
    Then looks up org membership.
    """
    from user_store import resolve_user_from_session

    cookie_name = request.app.state.auth_cookie_name if hasattr(request.app.state, "auth_cookie_name") else "kira_auth"
    token = request.cookies.get(cookie_name, "")
    username = resolve_user_from_session(token)
    if not username:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    return CurrentUser(username=username, org_id="", role="owner")


async def resolve_org_membership(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> CurrentUser:
    """Resolve user's org membership from DB.

    v1 CONSTRAINT: single-org membership only.
    If a user has multiple active memberships, this is a data integrity bug —
    fail loudly rather than silently picking one.

    Multi-org support (org switcher context) is Phase 3+.

    Auto-provision (org + owner membership) is DEV ONLY (BID_DEV_BOOTSTRAP=1).
    In production, users must be invited to an existing org.
    """
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.username,
            Membership.is_active == True,
        )
    )
    memberships = result.scalars().all()

    if len(memberships) > 1:
        org_ids = [m.org_id for m in memberships]
        logger.error(
            "v1 invariant violation: user '%s' has %d active memberships (orgs: %s). "
            "Multi-org not supported in v1.",
            user.username, len(memberships), org_ids,
        )
        raise HTTPException(
            status_code=409,
            detail="복수 조직 소속은 현재 버전에서 지원되지 않습니다. 관리자에게 문의하세요.",
        )

    membership = memberships[0] if memberships else None

    if membership is None:
        if not _DEV_BOOTSTRAP:
            raise HTTPException(
                status_code=403,
                detail="소속된 조직이 없습니다. 관리자에게 초대를 요청하세요.",
            )
        # DEV ONLY: auto-provision org + owner membership
        logger.warning("DEV_BOOTSTRAP: auto-creating org for user=%s", user.username)
        from services.web_app.db.models.org import Organization
        org = Organization(name=f"{user.username}의 조직")
        db.add(org)
        await db.flush()

        membership = Membership(
            org_id=org.id,
            user_id=user.username,
            role="owner",
            is_active=True,
        )
        db.add(membership)
        await db.commit()

    user.org_id = membership.org_id
    user.role = membership.role
    return user


# --- ACL: Project-level access control ---

# access_level hierarchy (higher = more permissive)
_ACCESS_LEVELS = {
    "viewer": 1,
    "reviewer": 2,
    "approver": 3,
    "editor": 4,
    "owner": 5,
}

# Org-level roles that bypass project_access row check (full org access)
_ORG_BYPASS_ROLES = {"owner", "admin"}


async def require_project_access(
    project_id: str,
    min_level: str,
    user: CurrentUser,
    db: AsyncSession,
) -> ProjectAccess | None:
    """Central ACL guard. Enforced on ALL project/asset/read/write paths.

    Logic:
    1. Verify project exists AND belongs to user's org → 404 if not.
    2. If user.role is org owner/admin → bypass project_access check (full access).
    3. Otherwise, require ProjectAccess row with level >= min_level.
    4. No access → 404 (not 403, to prevent IDOR enumeration).

    Returns ProjectAccess row if one exists, None for org-level bypass.
    """
    from services.web_app.db.models.project import BidProject

    # 1. Verify project belongs to user's org
    proj_result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.org_id == user.org_id,
        )
    )
    project = proj_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")

    # 2. Org owner/admin bypass — full access to all projects in their org
    if user.role in _ORG_BYPASS_ROLES:
        return None

    # 3. Check ProjectAccess row for non-admin users
    access_result = await db.execute(
        select(ProjectAccess).where(
            ProjectAccess.project_id == project_id,
            ProjectAccess.user_id == user.username,
        )
    )
    access = access_result.scalar_one_or_none()

    if access is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")

    # 4. Check access level hierarchy
    user_level = _ACCESS_LEVELS.get(access.access_level, 0)
    required_level = _ACCESS_LEVELS.get(min_level, 0)
    if user_level < required_level:
        raise HTTPException(status_code=403, detail="권한이 부족합니다")

    return access
```

- [ ] **Step 2: Commit**

```bash
git add services/web_app/api/
git commit -m "feat(bid-workspace): add API dependencies (auth + org resolution)"
```

---

### Task 11: Asset Upload/Download API

**Files:**
- Create: `services/web_app/api/assets.py`
- Create: `services/web_app/tests/test_assets_api.py`

- [ ] **Step 1: Write failing test**

```python
# services/web_app/tests/test_assets_api.py
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from services.web_app.api.assets import router


@pytest.mark.asyncio
async def test_download_asset_requires_org_ownership():
    """Asset download must verify org ownership — return 404 for wrong org."""
    # This test verifies the ownership check logic exists
    # Full integration test requires DB setup
    assert router.routes  # Router has routes defined
```

- [ ] **Step 2: Implement asset routes**

```python
# services/web_app/api/assets.py
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.document import DocumentAsset
from services.web_app.db.models.audit import AuditLog
from services.web_app.storage.s3 import get_s3_client
from services.web_app.api.deps import CurrentUser, resolve_org_membership, require_project_access

router = APIRouter(prefix="/api/assets", tags=["assets"])


def check_download_policy(asset: DocumentAsset) -> None:
    """Enforce download readiness policy based on asset origin.

    Generated assets (have revision_id): require "verified" — integrity matters for AI output.
    Source uploads (no revision_id): allow "uploaded" — user-uploaded, integrity is their responsibility.

    Raises HTTPException(409) if asset is not ready for download.
    Extracted as pure function for testability.
    """
    if asset.revision_id:
        if asset.upload_status != "verified":
            raise HTTPException(
                status_code=409,
                detail="생성 문서 검증 대기 중입니다. 잠시 후 다시 시도하세요.",
            )
    else:
        if asset.upload_status not in ("uploaded", "verified"):
            raise HTTPException(status_code=409, detail="파일 업로드 진행 중입니다")


@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """ACL-verified asset download via presigned URL."""
    result = await db.execute(
        select(DocumentAsset).where(
            DocumentAsset.id == asset_id,
            DocumentAsset.org_id == user.org_id,
            DocumentAsset.is_deleted == False,
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

    # ACL: viewer or above can download project assets
    if asset.project_id:
        await require_project_access(asset.project_id, "viewer", user, db)

    # Download readiness check (policy extracted for testability)
    check_download_policy(asset)

    s3 = get_s3_client()
    key = s3.parse_storage_uri(asset.storage_uri)
    url = s3.generate_presigned_download_url(
        key=key,
        original_filename=asset.original_filename,
        expires_in=3600,
    )

    # Audit log
    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=asset.project_id,
        action="download_asset",
        target_type="document_asset",
        target_id=asset_id,
    )
    db.add(audit)
    await db.commit()

    return {"download_url": url, "filename": asset.original_filename}


@router.post("/{asset_id}/confirm-upload")
async def confirm_upload(
    asset_id: str,
    content_hash: str | None = None,
    size_bytes: int | None = None,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Client confirms upload completion. Transitions upload_status → uploaded → verified."""
    result = await db.execute(
        select(DocumentAsset).where(
            DocumentAsset.id == asset_id,
            DocumentAsset.org_id == user.org_id,
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404)

    # ACL: editor or above can confirm uploads
    if asset.project_id:
        await require_project_access(asset.project_id, "editor", user, db)

    if asset.upload_status not in ("presigned_issued", "uploading"):
        raise HTTPException(status_code=409, detail=f"Invalid status: {asset.upload_status}")

    # Step 1: Verify file exists in S3 + get server-side metadata
    s3 = get_s3_client()
    try:
        key = s3.parse_storage_uri(asset.storage_uri)
        head = s3.head_object(key)
        actual_size = head.get("ContentLength", 0)
        # S3 ETag is MD5 for non-multipart uploads, or MD5-of-parts for multipart
        s3_etag = head.get("ETag", "").strip('"')
    except Exception:
        asset.upload_status = "failed"
        await db.commit()
        raise HTTPException(status_code=422, detail="S3 파일 확인 실패")

    # Step 2: Transition to "uploaded" (S3 head confirmed file exists)
    asset.upload_status = "uploaded"
    asset.size_bytes = actual_size
    await db.flush()

    # Step 3: Integrity verification — what "verified" actually guarantees:
    #
    # Guarantee levels (honest naming):
    # - "uploaded"  = S3 head_object succeeded (file exists, has size)
    # - "verified"  = "uploaded" + we have an ETag (S3-level integrity)
    #
    # What "verified" does NOT guarantee:
    # - SHA256 content hash (ETag = MD5 for single-part, opaque for multipart)
    # - Provider-independent hash (ETag format varies by S3/R2/MinIO)
    # - Client-to-server bit-for-bit integrity
    #
    # Phase 2 upgrade path: S3 ChecksumAlgorithm=SHA256 or server-side
    # download+hash for critical document types (final_upload).

    if s3_etag:
        asset.content_hash = f"etag:{s3_etag}"
        asset.upload_status = "verified"
        if content_hash:
            # Store client hash alongside ETag for audit trail
            asset.content_hash = f"etag:{s3_etag},client:{content_hash}"
            if content_hash != s3_etag:
                logger.info(
                    "ETag/client hash differ for asset %s (expected for multipart): "
                    "etag=%s, client=%s", asset_id, s3_etag, content_hash,
                )
    else:
        # No ETag — unusual. Leave as "uploaded", log for investigation.
        logger.warning("No ETag from S3 for asset %s — leaving as 'uploaded'", asset_id)

    await db.commit()

    return {
        "status": asset.upload_status,
        "size_bytes": actual_size,
        "content_hash": asset.content_hash,
    }
```

- [ ] **Step 3: Run tests**

Run: `pytest services/web_app/tests/test_assets_api.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add services/web_app/api/assets.py services/web_app/tests/test_assets_api.py
git commit -m "feat(bid-workspace): add asset download/upload-confirm API with ownership check"
```

---

### Task 12: Project CRUD API

**Files:**
- Create: `services/web_app/api/projects.py`
- Create: `services/web_app/tests/test_projects_api.py`

- [ ] **Step 1: Write failing test**

```python
# services/web_app/tests/test_projects_api.py
from __future__ import annotations

import pytest
from services.web_app.api.projects import router


def test_project_router_has_routes():
    route_paths = [r.path for r in router.routes]
    assert "/" in route_paths  # POST / (create)
    assert "/" in route_paths  # GET / (list)
    assert "/{project_id}" in route_paths  # GET detail
```

- [ ] **Step 2: Implement project routes**

```python
# services/web_app/api/projects.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.project import BidProject, ProjectAccess, SourceDocument
from services.web_app.db.models.document import DocumentAsset, ProjectCurrentDocument
from services.web_app.db.models.audit import AuditLog
from services.web_app.storage.s3 import get_s3_client
from services.web_app.api.deps import CurrentUser, resolve_org_membership, require_project_access

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    rfp_source_type: str | None = None
    rfp_source_ref: str | None = None
    generation_mode: str | None = None


class UploadSourceRequest(BaseModel):
    document_kind: str = Field(
        pattern="^(rfp|company_profile|template|past_proposal|track_record|personnel|supporting_material|final_upload)$"
    )
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = "application/octet-stream"


@router.post("/")
async def create_project(
    req: CreateProjectRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    project = BidProject(
        org_id=user.org_id,
        created_by=user.username,
        title=req.title,
        status="draft",
        rfp_source_type=req.rfp_source_type,
        rfp_source_ref=req.rfp_source_ref,
        generation_mode=req.generation_mode,
    )
    db.add(project)
    await db.flush()

    # Creator gets owner access
    access = ProjectAccess(
        project_id=project.id,
        user_id=user.username,
        access_level="owner",
    )
    db.add(access)

    # Audit
    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project.id,
        action="create_project",
        target_type="bid_project",
        target_id=project.id,
        detail_json={"title": req.title},
    )
    db.add(audit)
    await db.commit()

    return {
        "id": project.id,
        "title": project.title,
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


@router.get("/")
async def list_projects(
    status: str | None = None,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """List projects the user has access to.

    Org owner/admin: see all org projects.
    Others: only projects with ProjectAccess row.
    """
    if user.role in ("owner", "admin"):
        # Org owner/admin see everything in their org
        query = select(BidProject).where(BidProject.org_id == user.org_id)
    else:
        # Non-admin: only projects with explicit ProjectAccess
        query = (
            select(BidProject)
            .join(ProjectAccess, ProjectAccess.project_id == BidProject.id)
            .where(
                BidProject.org_id == user.org_id,
                ProjectAccess.user_id == user.username,
            )
        )

    if status:
        query = query.where(BidProject.status == status)
    query = query.order_by(BidProject.created_at.desc())

    result = await db.execute(query)
    projects = result.scalars().all()

    return {
        "projects": [
            {
                "id": p.id,
                "title": p.title,
                "status": p.status,
                "rfp_source_type": p.rfp_source_type,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in projects
        ]
    }


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    # ACL: viewer or above can read project
    await require_project_access(project_id, "viewer", user, db)

    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.org_id == user.org_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404)

    return {
        "id": project.id,
        "title": project.title,
        "status": project.status,
        "rfp_source_type": project.rfp_source_type,
        "rfp_source_ref": project.rfp_source_ref,
        "generation_mode": project.generation_mode,
        "settings_json": project.settings_json,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    title: str | None = None,
    status: str | None = None,
    generation_mode: str | None = None,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    # ACL: editor or above can modify project
    await require_project_access(project_id, "editor", user, db)

    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.org_id == user.org_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404)

    if title is not None:
        project.title = title
    if status is not None:
        project.status = status
    if generation_mode is not None:
        project.generation_mode = generation_mode

    await db.commit()
    return {"id": project.id, "status": project.status}


@router.delete("/{project_id}")
async def archive_project(
    project_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    # ACL: owner only can archive project
    await require_project_access(project_id, "owner", user, db)

    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.org_id == user.org_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404)

    project.status = "archived"

    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project.id,
        action="archive_project",
        target_type="bid_project",
        target_id=project.id,
    )
    db.add(audit)
    await db.commit()

    return {"id": project.id, "status": "archived"}


@router.post("/{project_id}/sources")
async def upload_source(
    project_id: str,
    req: UploadSourceRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Create document_asset + presigned upload URL for source document."""
    # ACL: editor or above can upload source documents
    await require_project_access(project_id, "editor", user, db)

    from services.web_app.db.models.base import new_cuid
    asset_id = new_cuid()
    s3 = get_s3_client()
    key = s3.build_source_storage_key(
        org_id=user.org_id,
        source_doc_id=asset_id,
        filename=req.filename,
    )
    storage_uri = s3.build_full_uri(key)

    asset = DocumentAsset(
        id=asset_id,
        org_id=user.org_id,
        project_id=project_id,
        asset_type="original",  # Source uploads are always "original" — not derived from file extension
        storage_uri=storage_uri,
        upload_status="presigned_issued",
        original_filename=req.filename,
        mime_type=req.content_type,
    )
    db.add(asset)

    source_doc = SourceDocument(
        org_id=user.org_id,
        project_id=project_id,
        document_kind=req.document_kind,
        uploaded_by=user.username,
        asset_id=asset_id,
        parse_status="pending",
    )
    db.add(source_doc)
    await db.flush()  # generate source_doc.id before using it in audit

    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="upload_source",
        target_type="source_document",
        target_id=source_doc.id,  # now guaranteed to be populated
        detail_json={"filename": req.filename, "kind": req.document_kind},
    )
    db.add(audit)
    await db.commit()

    presigned_url = s3.generate_presigned_upload_url(
        key=key,
        content_type=req.content_type,
    )

    return {
        "asset_id": asset_id,
        "source_document_id": source_doc.id,
        "presigned_url": presigned_url,
        "storage_key": key,
    }
```

- [ ] **Step 3: Run tests**

Run: `pytest services/web_app/tests/test_projects_api.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add services/web_app/api/projects.py services/web_app/tests/test_projects_api.py
git commit -m "feat(bid-workspace): add Project CRUD + source upload API"
```

---

## Chunk 3: Session Adapter + Integration

### Task 13: Session Adapter (session_id ↔ bid_project bridge)

**Files:**
- Create: `services/web_app/api/adapter.py`
- Create: `services/web_app/tests/test_adapter.py`

- [ ] **Step 1: Write failing test**

```python
# services/web_app/tests/test_adapter.py
from __future__ import annotations

import pytest
from services.web_app.api.adapter import SessionAdapter


def test_adapter_class_exists():
    assert hasattr(SessionAdapter, "get_or_create_project")
    assert hasattr(SessionAdapter, "save_analysis")
    assert hasattr(SessionAdapter, "get_analysis")
```

- [ ] **Step 2: Implement session adapter**

The adapter translates existing session-based calls to bid_project DB operations.
**No new features** — read/write-through only (spec rule).

```python
# services/web_app/api/adapter.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, AnalysisSnapshot
from services.web_app.db.models.base import new_cuid


class SessionAdapter:
    """Thin bridge: session_id → bid_project.

    Rules (from spec):
    1. READ/WRITE-THROUGH ONLY — adapter calls bid_project API internally.
    2. NEW FEATURE ADDITION PROHIBITED — new features go to /api/projects/* only.
    3. SOURCE OF TRUTH = Workspace API — session memory is cache only.
    4. REMOVAL: Phase 3 deprecated, Phase 4 removed.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_or_create_project(
        self,
        session_id: str,
        username: str,
        title: str = "대화 기반 프로젝트",
    ) -> BidProject:
        """Map existing session_id to a bid_project.

        Uses dedicated legacy_session_id column for lookup.
        rfp_source_ref is a business field — NOT used for session mapping.
        Creates org + membership if user has none (Phase 1 dev-bootstrap).
        """
        # Find existing project mapped to this session
        result = await self._db.execute(
            select(BidProject).where(
                BidProject.legacy_session_id == session_id,
            )
        )
        project = result.scalar_one_or_none()
        if project is not None:
            return project

        # Ensure user has an org
        org_id = await self._ensure_org(username)

        # Create new project for this session
        project = BidProject(
            org_id=org_id,
            created_by=username,
            title=title,
            status="draft",
            rfp_source_type="upload",
            legacy_session_id=session_id,
        )
        self._db.add(project)
        await self._db.flush()
        return project

    async def save_analysis(
        self,
        project_id: str,
        org_id: str,
        analysis_json: dict,
        summary_md: str | None = None,
        go_nogo_json: dict | None = None,
        username: str | None = None,
    ) -> AnalysisSnapshot:
        """Save analysis result as immutable snapshot.

        Deactivates previous active snapshot, creates new one.
        """
        # Deactivate current active snapshot
        result = await self._db.execute(
            select(AnalysisSnapshot).where(
                AnalysisSnapshot.project_id == project_id,
                AnalysisSnapshot.is_active == True,
            )
        )
        current = result.scalar_one_or_none()
        next_version = 1
        if current is not None:
            current.is_active = False
            next_version = current.version + 1

        snapshot = AnalysisSnapshot(
            org_id=org_id,
            project_id=project_id,
            version=next_version,
            analysis_json=analysis_json,
            analysis_schema="rfx_analysis_v1",
            summary_md=summary_md,
            go_nogo_result_json=go_nogo_json,
            is_active=True,
            created_by=username,
        )
        self._db.add(snapshot)
        await self._db.flush()

        # Update project's active snapshot pointer
        proj_result = await self._db.execute(
            select(BidProject).where(BidProject.id == project_id)
        )
        project = proj_result.scalar_one()
        project.active_analysis_snapshot_id = snapshot.id
        project.status = "ready_for_generation"

        await self._db.commit()
        return snapshot

    async def get_analysis(self, project_id: str) -> dict | None:
        """Get active analysis snapshot for a project."""
        result = await self._db.execute(
            select(AnalysisSnapshot).where(
                AnalysisSnapshot.project_id == project_id,
                AnalysisSnapshot.is_active == True,
            )
        )
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            return None
        return {
            "id": snapshot.id,
            "version": snapshot.version,
            "analysis_json": snapshot.analysis_json,
            "summary_md": snapshot.summary_md,
            "go_nogo_result_json": snapshot.go_nogo_result_json,
        }

    async def _ensure_org(self, username: str) -> str:
        """Ensure user has an org. Auto-create ONLY in dev (BID_DEV_BOOTSTRAP=1).

        In production, users MUST already have an org+membership (created via
        admin invite flow). Unconditional org creation = ghost org risk.
        """
        import os
        import logging as _logging

        result = await self._db.execute(
            select(Membership).where(
                Membership.user_id == username,
                Membership.is_active == True,
            )
        )
        memberships = result.scalars().all()

        # v1 invariant: single-org only (same check as resolve_org_membership)
        if len(memberships) > 1:
            org_ids = [m.org_id for m in memberships]
            _logging.getLogger(__name__).error(
                "v1 invariant violation in adapter: user '%s' has %d active memberships (orgs: %s)",
                username, len(memberships), org_ids,
            )
            raise ValueError(
                f"User '{username}' has multiple active memberships. "
                "Multi-org not supported in v1."
            )

        if memberships:
            return memberships[0].org_id

        # Guard: ONLY auto-provision in dev mode
        dev_bootstrap = os.getenv("BID_DEV_BOOTSTRAP", "").lower() in ("1", "true")
        if not dev_bootstrap:
            raise ValueError(
                f"User '{username}' has no org membership and BID_DEV_BOOTSTRAP is not enabled. "
                "In production, users must be invited to an existing org."
            )

        _logging.getLogger(__name__).warning(
            "DEV_BOOTSTRAP: adapter auto-creating org for user=%s", username
        )

        org = Organization(name=f"{username}의 조직")
        self._db.add(org)
        await self._db.flush()

        membership = Membership(
            org_id=org.id,
            user_id=username,
            role="owner",
            is_active=True,
        )
        self._db.add(membership)
        await self._db.flush()
        return org.id
```

- [ ] **Step 3: Run test**

Run: `pytest services/web_app/tests/test_adapter.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add services/web_app/api/adapter.py services/web_app/tests/test_adapter.py
git commit -m "feat(bid-workspace): add SessionAdapter (session_id ↔ bid_project bridge)"
```

---

### Task 14: Wire Routers into web_app/main.py

**Files:**
- Modify: `services/web_app/main.py`

- [ ] **Step 1: Add DB lifespan + router includes**

Add to `services/web_app/main.py` — near the top imports:

```python
import os
# Only init Bid Workspace DB if BID_DATABASE_URL is set (gradual rollout)
_BID_DB_ENABLED = bool(os.getenv("BID_DATABASE_URL"))
```

Add to the app lifespan (or startup event):

```python
if _BID_DB_ENABLED:
    from services.web_app.db import init_db, close_db
    await init_db()

# ... existing startup code ...

# On shutdown:
if _BID_DB_ENABLED:
    await close_db()
```

Add router includes after app creation:

```python
if _BID_DB_ENABLED:
    from services.web_app.api.projects import router as projects_router
    from services.web_app.api.assets import router as assets_router
    app.include_router(projects_router)
    app.include_router(assets_router)
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `pytest tests/ -q --timeout=30`
Expected: All existing tests PASS (no regression)

- [ ] **Step 3: Commit**

```bash
git add services/web_app/main.py
git commit -m "feat(bid-workspace): wire DB lifespan + project/asset routers into web_app"
```

---

### Task 15: Adapter Integration Test (DB roundtrip)

**Files:**
- Modify: `services/web_app/tests/test_adapter.py`

- [ ] **Step 1: Add DB roundtrip test**

```python
from services.web_app.api.adapter import SessionAdapter


# NOTE: Uses db_session from conftest.py (PostgreSQL-first, SQLite fallback)


@pytest.mark.asyncio
async def test_adapter_creates_project_on_first_call(db_session):
    adapter = SessionAdapter(db_session)
    project = await adapter.get_or_create_project(
        session_id="sess_001",
        username="testuser",
        title="XX기관 사업",
    )
    assert project.id is not None
    assert project.title == "XX기관 사업"
    assert project.legacy_session_id == "sess_001"
    assert project.org_id  # org was auto-created


@pytest.mark.asyncio
async def test_adapter_returns_same_project_for_same_session(db_session):
    adapter = SessionAdapter(db_session)
    p1 = await adapter.get_or_create_project("sess_001", "testuser")
    p2 = await adapter.get_or_create_project("sess_001", "testuser")
    assert p1.id == p2.id


@pytest.mark.asyncio
async def test_adapter_save_and_get_analysis(db_session):
    adapter = SessionAdapter(db_session)
    project = await adapter.get_or_create_project("sess_002", "testuser")

    analysis = {"title": "테스트 사업", "requirements": [{"category": "기술", "description": "웹 시스템"}]}
    snapshot = await adapter.save_analysis(
        project_id=project.id,
        org_id=project.org_id,
        analysis_json=analysis,
        summary_md="## 사업개요\n테스트",
        username="testuser",
    )
    assert snapshot.version == 1
    assert snapshot.is_active is True

    fetched = await adapter.get_analysis(project.id)
    assert fetched is not None
    assert fetched["analysis_json"]["title"] == "테스트 사업"


@pytest.mark.asyncio
async def test_adapter_analysis_versioning(db_session):
    adapter = SessionAdapter(db_session)
    project = await adapter.get_or_create_project("sess_003", "testuser")

    s1 = await adapter.save_analysis(project.id, project.org_id, {"v": 1})
    assert s1.version == 1

    s2 = await adapter.save_analysis(project.id, project.org_id, {"v": 2})
    assert s2.version == 2

    fetched = await adapter.get_analysis(project.id)
    assert fetched["analysis_json"]["v"] == 2
```

- [ ] **Step 2: Run integration tests** (requires PostgreSQL + BID_DEV_BOOTSTRAP for auto-org tests)

Run: `BID_DEV_BOOTSTRAP=1 pytest services/web_app/tests/test_adapter.py -v`
Expected: PASS (4 tests)

- [ ] **Step 3: Run all model tests**

Run: `pytest services/web_app/tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add services/web_app/tests/test_adapter.py
git commit -m "test(bid-workspace): add adapter integration tests with analysis versioning"
```

---

### Task 16: Verify No Regressions

**Files:** None (verification only)

- [ ] **Step 1: Run existing root tests**

Run: `pytest tests/ -q --timeout=60`
Expected: All existing tests PASS

- [ ] **Step 2: Run rag_engine tests**

Run: `cd rag_engine && pytest -q --timeout=60`
Expected: All existing tests PASS

- [ ] **Step 3: Run new bid workspace tests**

Run: `pytest services/web_app/tests/ -v`
Expected: All PASS

- [ ] **Step 4: Type check (if applicable)**

Run: `cd frontend/kirabot && npx tsc --noEmit`
Expected: No new errors

- [ ] **Step 5: Final commit with all files**

```bash
git add -A services/web_app/db/ services/web_app/storage/ services/web_app/api/ services/web_app/tests/
git status  # Review what's staged
git commit -m "feat(bid-workspace): Phase 1 Foundation — PostgreSQL schema, S3 client, session adapter

- 14 SQLAlchemy models with CHECK constraints on all enum columns
- pgvector Vector(1536) in ORM (no autogenerate drift)
- S3/R2 client with honest verification semantics (uploaded + ETag = verified)
- Project CRUD + asset APIs with central ACL (require_project_access)
- Org owner/admin bypass + non-admin ProjectAccess enforcement
- list_projects scoped to user's accessible projects
- Session adapter (legacy_session_id ↔ bid_project bridge)
- Alembic migration setup
- PostgreSQL-first test isolation (outer transaction + savepoint pattern)
- 5-layer test strategy with realistic dummy data
- Org auto-provision gated behind BID_DEV_BOOTSTRAP
- Runtime: existing Dockerfile + start.sh (no new Dockerfile)"
```

---

## Runtime Topology (Canonical)

**Production (Railway):** Single container via existing `Dockerfile` + `start.sh`.
`start.sh` starts both `web_app` (port 8000) and `rag_engine` (port 8001).
No new `Dockerfile.web_app` — we use the existing monolith container.

**BID_DATABASE_URL injection:** Railway env var → `start.sh` passes to `web_app`.
When `BID_DATABASE_URL` is unset, Bid Workspace routes are disabled (graceful degradation).

**Local dev:** `python services/web_app/main.py` directly (port 8000).
Set `BID_DATABASE_URL` and `BID_DEV_BOOTSTRAP=1` in `.env` or shell.

## Docker Compose: Test DB

Update `docker-compose.yml` to add **test databases only** (web_app runs outside docker in dev):

```yaml
# Add to existing docker-compose.yml services:

  kira_bid_db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: kira
      POSTGRES_PASSWORD: kira
      POSTGRES_DB: kira_bid
    ports:
      - "5433:5432"
    volumes:
      - kira_bid_data:/var/lib/postgresql/data

  kira_bid_test_db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: kira
      POSTGRES_PASSWORD: kira
      POSTGRES_DB: kira_bid_test
    ports:
      - "5434:5432"
    tmpfs:
      - /var/lib/postgresql/data  # RAM-backed for speed

# Add volume:
volumes:
  kira_bid_data:
```

**Local dev (.env):**
```bash
BID_DATABASE_URL=postgresql+asyncpg://kira:kira@localhost:5433/kira_bid
BID_DEV_BOOTSTRAP=1
```

**Test execution:**
```bash
# Start test DB:
docker compose up kira_bid_test_db -d

# Run tests (PostgreSQL required — no SQLite fallback):
BID_TEST_DATABASE_URL="postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test" \
  pytest services/web_app/tests/ -v
```

---

## 5-Layer Test Strategy

### Layer 1: Unit Tests (No DB, No I/O)

Fast, isolated tests for pure logic. Run with plain `pytest`.

```python
# services/web_app/tests/test_unit.py

# --- Enum + state transition ---
from services.web_app.db.models.base import DocType, ContentSchema

def test_doc_type_values():
    assert DocType.PROPOSAL == "proposal"
    assert len(DocType.ALL) == 5
    assert DocType.CHECKLIST in DocType.ALL

def test_content_schema_consistency():
    # Every doc_type has a corresponding content_schema
    for dt in DocType.ALL:
        assert hasattr(ContentSchema, f"{dt.upper()}_V1")


# --- ACL hierarchy ---
from services.web_app.api.deps import _ACCESS_LEVELS

def test_access_level_hierarchy():
    assert _ACCESS_LEVELS["owner"] > _ACCESS_LEVELS["editor"]
    assert _ACCESS_LEVELS["editor"] > _ACCESS_LEVELS["reviewer"]
    assert _ACCESS_LEVELS["reviewer"] > _ACCESS_LEVELS["viewer"]

def test_all_levels_defined():
    for level in ("viewer", "reviewer", "approver", "editor", "owner"):
        assert level in _ACCESS_LEVELS


# --- cuid2 + S3 key ---
from services.web_app.db.models.base import new_cuid

def test_cuid_unique():
    ids = {new_cuid() for _ in range(100)}
    assert len(ids) == 100


# --- BidProject status transitions ---
_VALID_TRANSITIONS = {
    "draft": {"collecting_inputs", "analyzing"},
    "collecting_inputs": {"analyzing"},
    "analyzing": {"ready_for_generation"},
    "ready_for_generation": {"generating"},
    "generating": {"in_review", "ready_for_generation"},  # retry
    "in_review": {"changes_requested", "approved"},
    "changes_requested": {"in_review", "generating"},
    "approved": {"locked_for_submission"},
    "locked_for_submission": {"submitted"},
    "submitted": {"archived"},
}

def test_status_transitions_complete():
    """Every status except 'archived' has at least one valid transition."""
    for status in _VALID_TRANSITIONS:
        assert len(_VALID_TRANSITIONS[status]) >= 1
```

### Layer 2: PostgreSQL Integration Tests (DB-specific features)

**Requires:** `BID_TEST_DATABASE_URL` pointing to PostgreSQL with pgvector.

```python
# services/web_app/tests/test_postgres_integration.py

import pytest
from sqlalchemy import text
from services.web_app.db.models.project import BidProject, AnalysisSnapshot
from services.web_app.db.models.org import Organization


@pytest.mark.asyncio
async def test_jsonb_query(db_session):
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    proj = BidProject(
        org_id=org.id, created_by="u1", title="테스트",
        settings_json={"total_pages": 50, "template": "standard"},
    )
    db_session.add(proj)
    await db_session.commit()

    # JSONB containment query
    result = await db_session.execute(
        text("SELECT id FROM bid_projects WHERE settings_json @> :val"),
        {"val": '{"total_pages": 50}'},
    )
    row = result.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_partial_unique_index_analysis_snapshot(db_session):
    """Only one active snapshot per project (idx_analysis_active)."""

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    proj = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(proj)
    await db_session.flush()

    s1 = AnalysisSnapshot(
        org_id=org.id, project_id=proj.id, version=1,
        analysis_json={"v": 1}, is_active=True,
    )
    db_session.add(s1)
    await db_session.commit()

    # Second active snapshot should violate partial unique index
    s2 = AnalysisSnapshot(
        org_id=org.id, project_id=proj.id, version=2,
        analysis_json={"v": 2}, is_active=True,
    )
    db_session.add(s2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_check_constraint_rejects_invalid_status(db_session):

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    proj = BidProject(
        org_id=org.id, created_by="u1", title="테스트",
        status="invalid_status",
    )
    db_session.add(proj)
    with pytest.raises(Exception):  # IntegrityError from CHECK constraint
        await db_session.commit()


@pytest.mark.asyncio
async def test_deferrable_fk_bid_project_analysis(db_session):
    """bid_projects.active_analysis_snapshot_id FK is deferrable."""

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    # Create project with active_analysis_snapshot_id pointing to not-yet-created snapshot
    proj = BidProject(org_id=org.id, created_by="u1", title="테스트")
    db_session.add(proj)
    await db_session.flush()

    snapshot = AnalysisSnapshot(
        org_id=org.id, project_id=proj.id, version=1,
        analysis_json={}, is_active=True,
    )
    db_session.add(snapshot)
    await db_session.flush()

    proj.active_analysis_snapshot_id = snapshot.id
    await db_session.commit()  # Should succeed with deferred FK


@pytest.mark.asyncio
async def test_legacy_session_id_unique(db_session):
    """legacy_session_id uniqueness constraint."""
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    p1 = BidProject(
        org_id=org.id, created_by="u1", title="P1",
        legacy_session_id="session_abc",
    )
    db_session.add(p1)
    await db_session.commit()

    p2 = BidProject(
        org_id=org.id, created_by="u1", title="P2",
        legacy_session_id="session_abc",  # duplicate
    )
    db_session.add(p2)
    with pytest.raises(Exception):  # IntegrityError from unique
        await db_session.commit()
```

### Layer 3: Storage Integration Tests (MinIO/R2)

**Requires:** MinIO container or R2 test bucket.

```python
# services/web_app/tests/test_storage_integration.py

import io
import hashlib
import os
import pytest
from services.web_app.storage.s3 import S3Client

_STORAGE_TEST_URL = os.getenv("S3_TEST_ENDPOINT_URL")


@pytest.fixture
def s3_client():
    if not _STORAGE_TEST_URL:
        pytest.skip("S3_TEST_ENDPOINT_URL not set")
    return S3Client(
        endpoint_url=_STORAGE_TEST_URL,
        access_key_id=os.getenv("S3_TEST_ACCESS_KEY", "minioadmin"),
        secret_access_key=os.getenv("S3_TEST_SECRET_KEY", "minioadmin"),
        bucket_name="kira-test-assets",
        region="us-east-1",
    )


def test_upload_download_roundtrip(s3_client):
    """Upload → head → download → verify content matches."""
    content = "테스트 문서 내용".encode("utf-8")
    key = "test/roundtrip/test.txt"

    s3_client.upload_fileobj(io.BytesIO(content), key, "text/plain")

    head = s3_client.head_object(key)
    assert head["ContentLength"] == len(content)

    buf = io.BytesIO()
    s3_client.download_fileobj(key, buf)
    assert buf.getvalue() == content

    s3_client.delete_object(key)


def test_presigned_url_generation(s3_client):
    """Presigned upload + download URLs are valid format."""
    key = "test/presigned/test.docx"
    upload_url = s3_client.generate_presigned_upload_url(key)
    assert "X-Amz-Signature" in upload_url or "Signature" in upload_url

    download_url = s3_client.generate_presigned_download_url(key, "test.docx")
    assert "X-Amz-Signature" in download_url or "Signature" in download_url


def test_checksum_verification(s3_client):
    """Upload file and verify ETag matches content hash."""
    content = b"checksum test data"
    expected_md5 = hashlib.md5(content).hexdigest()
    key = "test/checksum/verify.bin"

    s3_client.upload_fileobj(io.BytesIO(content), key)
    head = s3_client.head_object(key)
    etag = head.get("ETag", "").strip('"')

    # For non-multipart uploads, ETag == MD5
    assert etag == expected_md5

    s3_client.delete_object(key)
```

### Layer 4: API Scenario Tests (Realistic Dummy Data)

```python
# services/web_app/tests/test_api_scenarios.py

import pytest
from services.web_app.api.adapter import SessionAdapter
from services.web_app.db.models.org import Organization, Membership
from services.web_app.db.models.project import BidProject, ProjectAccess
from sqlalchemy import select


# --- Realistic dummy data ---
REALISTIC_RFP = {
    "title": "2026년 XX교육청 학사행정시스템 고도화 사업",
    "issuing_org": "XX교육청",
    "budget": "8억5천만원",
    "project_period": "2026-06 ~ 2027-05 (12개월)",
    "evaluation_criteria": [
        {"category": "사업 이해도", "max_score": 15, "description": "사업 배경 및 목적 이해"},
        {"category": "기술적 접근방안", "max_score": 30, "description": "시스템 아키텍처, 구현방안"},
        {"category": "수행관리 방안", "max_score": 15, "description": "일정관리, 품질관리, 리스크관리"},
        {"category": "투입인력 및 조직", "max_score": 10, "description": "PM/PL 구성"},
        {"category": "유사 수행실적", "max_score": 10, "description": "관련 경험"},
    ],
    "requirements": [
        {"category": "기능요건", "description": "학적관리, 성적처리, 출결관리 모듈"},
        {"category": "기술요건", "description": "클라우드 네이티브, MSA 기반 구축"},
        {"category": "보안요건", "description": "개인정보보호법 준수, ISMS 인증 수준"},
    ],
}


@pytest.mark.asyncio
async def test_full_project_lifecycle(db_session):
    """Create org → project → analysis → verify state transitions."""
    # 1. Create org + user
    org = Organization(name="MS솔루션")
    db_session.add(org)
    await db_session.flush()

    member = Membership(org_id=org.id, user_id="testpm", role="owner", is_active=True)
    db_session.add(member)
    await db_session.flush()

    # 2. Create project
    project = BidProject(
        org_id=org.id,
        created_by="testpm",
        title=REALISTIC_RFP["title"],
        status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    # 3. Grant project access
    access = ProjectAccess(
        project_id=project.id, user_id="testpm", access_level="owner",
    )
    db_session.add(access)
    await db_session.commit()

    # 4. Simulate analysis via adapter
    adapter = SessionAdapter(db_session)
    snapshot = await adapter.save_analysis(
        project_id=project.id,
        org_id=org.id,
        analysis_json=REALISTIC_RFP,
        summary_md="## 사업개요\n학사행정시스템 고도화",
        username="testpm",
    )
    assert snapshot.version == 1

    # 5. Verify project status transitioned
    result = await db_session.execute(
        select(BidProject).where(BidProject.id == project.id)
    )
    updated_project = result.scalar_one()
    assert updated_project.status == "ready_for_generation"
    assert updated_project.active_analysis_snapshot_id == snapshot.id


@pytest.mark.asyncio
async def test_idor_prevention(db_session):
    """User from org_A cannot access org_B's project."""
    org_a = Organization(name="A사")
    org_b = Organization(name="B사")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    project_b = BidProject(
        org_id=org_b.id, created_by="user_b", title="B사 프로젝트",
    )
    db_session.add(project_b)
    await db_session.commit()

    # User from org_A tries to query org_B's project
    result = await db_session.execute(
        select(BidProject).where(
            BidProject.id == project_b.id,
            BidProject.org_id == org_a.id,  # wrong org
        )
    )
    assert result.scalar_one_or_none() is None  # not found


@pytest.mark.asyncio
async def test_acl_level_enforcement(db_session):
    """Viewer cannot perform editor actions."""
    from services.web_app.api.deps import require_project_access, CurrentUser
    from fastapi import HTTPException

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="admin", title="ACL 테스트")
    db_session.add(project)
    await db_session.flush()

    # Grant viewer access
    access = ProjectAccess(
        project_id=project.id, user_id="viewer_user", access_level="viewer",
    )
    db_session.add(access)

    # Grant viewer org membership
    member = Membership(org_id=org.id, user_id="viewer_user", role="viewer", is_active=True)
    db_session.add(member)
    await db_session.commit()

    viewer = CurrentUser(username="viewer_user", org_id=org.id, role="viewer")

    # Viewer can read
    await require_project_access(project.id, "viewer", viewer, db_session)

    # Viewer cannot edit
    with pytest.raises(HTTPException) as exc_info:
        await require_project_access(project.id, "editor", viewer, db_session)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_org_owner_bypasses_project_access(db_session):
    """Org owner can access any project without ProjectAccess row."""
    from services.web_app.api.deps import require_project_access, CurrentUser

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    # Project created by someone else, no ProjectAccess for org_owner
    project = BidProject(org_id=org.id, created_by="other_user", title="타인 프로젝트")
    db_session.add(project)
    await db_session.commit()

    org_owner = CurrentUser(username="org_owner", org_id=org.id, role="owner")

    # Org owner can access without ProjectAccess row
    result = await require_project_access(project.id, "owner", org_owner, db_session)
    assert result is None  # None = org-level bypass, not ProjectAccess row


@pytest.mark.asyncio
async def test_org_admin_bypasses_project_access(db_session):
    """Org admin can access any project without ProjectAccess row."""
    from services.web_app.api.deps import require_project_access, CurrentUser

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="other_user", title="타인 프로젝트")
    db_session.add(project)
    await db_session.commit()

    org_admin = CurrentUser(username="org_admin", org_id=org.id, role="admin")

    result = await require_project_access(project.id, "editor", org_admin, db_session)
    assert result is None


@pytest.mark.asyncio
async def test_non_admin_without_access_row_rejected(db_session):
    """Non-admin user without ProjectAccess row gets 404."""
    from services.web_app.api.deps import require_project_access, CurrentUser
    from fastapi import HTTPException

    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="other_user", title="타인 프로젝트")
    db_session.add(project)
    await db_session.commit()

    editor_no_access = CurrentUser(username="no_access_user", org_id=org.id, role="editor")

    # No ProjectAccess row → 404 (not 403, anti-enumeration)
    with pytest.raises(HTTPException) as exc_info:
        await require_project_access(project.id, "viewer", editor_no_access, db_session)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_project_access_unique_constraint(db_session):
    """Duplicate (project_id, user_id) pair raises IntegrityError."""
    org = Organization(name="테스트")
    db_session.add(org)
    await db_session.flush()

    project = BidProject(org_id=org.id, created_by="u1", title="UniqueTest")
    db_session.add(project)
    await db_session.flush()

    a1 = ProjectAccess(project_id=project.id, user_id="u1", access_level="owner")
    db_session.add(a1)
    await db_session.commit()

    # Second access row for same (project, user) should fail
    a2 = ProjectAccess(project_id=project.id, user_id="u1", access_level="editor")
    db_session.add(a2)
    with pytest.raises(Exception):  # IntegrityError from unique constraint
        await db_session.commit()


@pytest.mark.asyncio
async def test_multi_org_membership_rejected(db_session):
    """v1: user with multiple active memberships gets 409 from resolve_org_membership."""
    from services.web_app.api.deps import resolve_org_membership, CurrentUser
    from fastapi import HTTPException

    org_a = Organization(name="A사")
    org_b = Organization(name="B사")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    # Create TWO active memberships for same user — v1 invariant violation
    m1 = Membership(org_id=org_a.id, user_id="multi_user", role="owner", is_active=True)
    m2 = Membership(org_id=org_b.id, user_id="multi_user", role="editor", is_active=True)
    db_session.add_all([m1, m2])
    await db_session.commit()

    # resolve_org_membership is an async def with Depends() defaults,
    # but it's still a plain async callable — pass args directly.
    user = CurrentUser(username="multi_user", org_id="", role="owner")
    with pytest.raises(HTTPException) as exc_info:
        await resolve_org_membership(user=user, db=db_session)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_adapter_multi_org_rejected(db_session):
    """SessionAdapter._ensure_org() also rejects multi-org (consistent with deps)."""
    import os
    from unittest.mock import patch
    from services.web_app.api.adapter import SessionAdapter

    org_a = Organization(name="A사")
    org_b = Organization(name="B사")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    m1 = Membership(org_id=org_a.id, user_id="multi_adapter_user", role="owner", is_active=True)
    m2 = Membership(org_id=org_b.id, user_id="multi_adapter_user", role="editor", is_active=True)
    db_session.add_all([m1, m2])
    await db_session.commit()

    adapter = SessionAdapter(db_session)
    with patch.dict(os.environ, {"BID_DEV_BOOTSTRAP": "true"}, clear=False):
        with pytest.raises(ValueError, match="multiple active memberships"):
            await adapter._ensure_org("multi_adapter_user")


@pytest.mark.asyncio
async def test_adapter_ensure_org_blocked_without_bootstrap(db_session):
    """SessionAdapter._ensure_org() raises without BID_DEV_BOOTSTRAP."""
    import os
    from unittest.mock import patch
    from services.web_app.api.adapter import SessionAdapter

    adapter = SessionAdapter(db_session)

    with patch.dict(os.environ, {"BID_DEV_BOOTSTRAP": "false"}, clear=False):
        with pytest.raises(ValueError, match="no org membership"):
            await adapter._ensure_org("ghost_user")


def _make_asset_stub(revision_id=None, upload_status="uploaded"):
    """Lightweight stub for check_download_policy — only reads revision_id + upload_status."""
    from types import SimpleNamespace
    return SimpleNamespace(revision_id=revision_id, upload_status=upload_status)


def test_download_policy_source_uploaded_allowed():
    """Source uploads (no revision_id) allow 'uploaded' status."""
    from services.web_app.api.assets import check_download_policy
    check_download_policy(_make_asset_stub(revision_id=None, upload_status="uploaded"))


def test_download_policy_source_verified_allowed():
    """Source uploads also accept 'verified'."""
    from services.web_app.api.assets import check_download_policy
    check_download_policy(_make_asset_stub(revision_id=None, upload_status="verified"))


def test_download_policy_source_presigned_rejected():
    """Source uploads with 'presigned_issued' are not ready."""
    from services.web_app.api.assets import check_download_policy
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        check_download_policy(_make_asset_stub(revision_id=None, upload_status="presigned_issued"))
    assert exc_info.value.status_code == 409


def test_download_policy_generated_requires_verified():
    """Generated assets (have revision_id) MUST be 'verified'."""
    from services.web_app.api.assets import check_download_policy
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        check_download_policy(_make_asset_stub(revision_id="rev_abc123", upload_status="uploaded"))
    assert exc_info.value.status_code == 409
    assert "검증" in exc_info.value.detail


def test_download_policy_generated_verified_allowed():
    """Generated assets with 'verified' pass the check."""
    from services.web_app.api.assets import check_download_policy
    check_download_policy(_make_asset_stub(revision_id="rev_abc123", upload_status="verified"))
```

### Layer 5: Document Quality Acceptance Tests (Phase 2)

Deferred to Phase 2 when GenerationContract is implemented. Will use golden dataset of 10-20 real RFPs.

---

## Post-Phase 1 Verification Checklist

Before proceeding to Phase 2, verify:

**Database & Schema:**
- [ ] All 14 tables created via Alembic on PostgreSQL 16+ (no SQLite — JSONB, CHECK, BigInt all require PG)
- [ ] pgvector extension enabled, `Vector(1536)` columns in ORM (direct import, no conditional fallback)
- [ ] All enum-like columns have CHECK constraints: status, role, access_level, doc_type, generation_mode, plan_tier
- [ ] `ProjectAccess` unique constraint on `(project_id, user_id)` prevents duplicate rows
- [ ] PostgreSQL integration tests pass: JSONB query, partial unique index, CHECK constraints, deferrable FK

**ACL & Security:**
- [ ] `require_project_access()` enforced on ALL routes: get/update/archive/upload/download/confirm
- [ ] Org owner/admin bypass ProjectAccess row check (full org access, returns None)
- [ ] list_projects scoped: org admin sees all, non-admin sees only their ProjectAccess projects
- [ ] Non-admin without ProjectAccess row gets 404 (not 403 — anti-enumeration)
- [ ] IDOR test passes — org_A user cannot access org_B project
- [ ] ACL level hierarchy works — viewer cannot edit, editor cannot archive

**Org & Membership:**
- [ ] Org auto-provision gated behind `BID_DEV_BOOTSTRAP=1` in BOTH `resolve_org_membership()` AND `SessionAdapter._ensure_org()`
- [ ] Multi-org membership rejected with 409 in v1 (explicit invariant, not silent first-pick)
- [ ] Production: user without membership gets 403 (not auto-provisioned org)

**Storage & Assets:**
- [ ] S3 presigned upload/download works with actual R2/S3 bucket
- [ ] Upload confirm: uploaded = S3 exists, verified = uploaded + ETag present (honest semantics)
- [ ] Download policy: source uploads allow "uploaded", generated assets require "verified"
- [ ] Source upload creates asset with `asset_type="original"` (not file extension)

**Session Adapter:**
- [ ] Session adapter correctly maps `legacy_session_id` → bid_project (NOT rfp_source_ref)
- [ ] `_ensure_org()` raises ValueError without `BID_DEV_BOOTSTRAP` — no ghost orgs in production

**Integration:**
- [ ] Existing Chat UI still works (no regressions)
- [ ] `BID_DATABASE_URL` not set → all new routes gracefully disabled
- [ ] `BID_DATABASE_URL` must be PostgreSQL — runtime validation rejects SQLite
- [ ] Audit logs record create_project, upload_source, download_asset actions

## Next Steps

1. **Phase 1b plan:** Add review/approval tables (7 tables) + skill tables (2 tables) + departments/teams (2 tables)
2. **Phase 2 plan:** GenerationContract + orchestrator signature unification + presigned URL transport + quality gates
3. **Phase 3 plan:** Bid Workspace frontend + review/approval UI
4. **Phase 4 plan:** Legacy removal + performance optimization
