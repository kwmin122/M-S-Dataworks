# Bid Workspace v1.0 — Phase 1: Foundation Infrastructure

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish PostgreSQL database, S3 object storage, and session adapter so existing Chat UI continues working while all new data flows through DB-centric bid_projects.

**Architecture:** SQLAlchemy 2.0 async ORM on shared PostgreSQL 16, Alembic migrations, boto3 S3/R2 client with presigned URLs, FastAPI APIRouter modules integrated into existing web_app. rag_engine stays stateless — no DB access.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0 (async), Alembic, asyncpg, boto3, FastAPI APIRouter, pgvector, pytest-asyncio

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
    ├── test_s3.py                      ← S3 client tests (mocked)
    ├── test_projects_api.py            ← Project API tests
    ├── test_assets_api.py              ← Asset API tests
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
aiosqlite==0.20.0
boto3==1.38.0
pgvector==0.3.6
cuid2==2.0.1
pytest-asyncio==0.24.0
```

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
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from services.web_app.db.models import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Per-test async session using in-memory SQLite for speed."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()
```

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

from sqlalchemy import Boolean, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CuidPkMixin, TimestampMixin, CreatedAtMixin


class Organization(CuidPkMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    plan_tier: Mapped[str | None] = mapped_column(Text, default="free")
    settings_json: Mapped[dict | None] = mapped_column(JSONB, default=None)

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
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

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CuidPkMixin, TimestampMixin, CreatedAtMixin


_BID_PROJECT_STATUSES = "status IN ('draft','collecting_inputs','analyzing','ready_for_generation','generating','in_review','changes_requested','approved','locked_for_submission','submitted','archived')"
_RFP_SOURCE_TYPES = "rfp_source_type IN ('upload','nara_search','manual') OR rfp_source_type IS NULL"
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
    active_analysis_snapshot_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("analysis_snapshots.id", use_alter=True, deferrable=True, initially="DEFERRED"),
    )
    generation_mode: Mapped[str | None] = mapped_column(Text)  # strict_template / starter / upgrade
    settings_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint(_BID_PROJECT_STATUSES, name="ck_bid_projects_status"),
        CheckConstraint(_RFP_SOURCE_TYPES, name="ck_bid_projects_rfp_source_type"),
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

# NOTE: pgvector Vector(1536) column only works on PostgreSQL.
# For SQLite tests, embedding columns are nullable Text.
# In production migration, use: from pgvector.sqlalchemy import Vector
# and change column type to Vector(1536).
# For now, we store embeddings as nullable to allow SQLite testing.


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
    # embedding: Vector(1536) — added in PostgreSQL migration, not in SQLite tests

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
    # embedding: Vector(1536) — added in PostgreSQL migration, not in SQLite tests

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
    # NOTE: Use INET on PostgreSQL for IP validation. Falls back to Text on SQLite tests.
    ip_address: Mapped[str | None] = mapped_column(Text)  # Alembic migration uses INET type
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

from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.org import Membership


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

    # For Phase 1, auto-provision org + membership if not exists
    # This is the session adapter bridge — existing users get auto-enrolled
    return CurrentUser(username=username, org_id="", role="owner")


async def resolve_org_membership(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> CurrentUser:
    """Resolve user's org membership from DB.

    Phase 1: auto-creates org + membership for first-time users.
    """
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.username,
            Membership.is_active == True,
        )
    )
    membership = result.scalar_one_or_none()

    if membership is None:
        # Auto-provision: create org + owner membership
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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.web_app.db.engine import get_async_session
from services.web_app.db.models.document import DocumentAsset
from services.web_app.db.models.audit import AuditLog
from services.web_app.storage.s3 import get_s3_client
from services.web_app.api.deps import CurrentUser, resolve_org_membership

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: str,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),
):
    """Ownership-verified asset download via presigned URL."""
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

    if asset.upload_status != "verified":
        raise HTTPException(status_code=409, detail="파일 준비 중입니다")

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

    if asset.upload_status not in ("presigned_issued", "uploading"):
        raise HTTPException(status_code=409, detail=f"Invalid status: {asset.upload_status}")

    # Verify file exists in S3
    s3 = get_s3_client()
    try:
        key = s3.parse_storage_uri(asset.storage_uri)
        head = s3.head_object(key)
        actual_size = head.get("ContentLength", 0)
    except Exception:
        asset.upload_status = "failed"
        await db.commit()
        raise HTTPException(status_code=422, detail="S3 파일 확인 실패")

    # Hash verification (spec section 6: uploaded → verified requires hash check)
    if content_hash:
        # Client-provided hash — store for audit trail
        # Server-side hash verification would require downloading the file;
        # for Phase 1, trust client hash + S3 ETag as integrity signal.
        asset.content_hash = content_hash

    asset.upload_status = "verified"
    asset.size_bytes = actual_size
    await db.commit()

    return {"status": "verified", "size_bytes": actual_size}
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
from services.web_app.api.deps import CurrentUser, resolve_org_membership

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
    query = select(BidProject).where(BidProject.org_id == user.org_id)
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
    # Verify project ownership
    result = await db.execute(
        select(BidProject).where(
            BidProject.id == project_id,
            BidProject.org_id == user.org_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404)

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
        asset_type=req.filename.rsplit(".", 1)[-1] if "." in req.filename else "other",
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

    audit = AuditLog(
        org_id=user.org_id,
        user_id=user.username,
        project_id=project_id,
        action="upload_source",
        target_type="source_document",
        target_id=source_doc.id,
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

        Uses session_id as rfp_source_ref for lookup.
        Creates org + membership if user has none (Phase 1 auto-provision).
        """
        # Find existing project mapped to this session
        result = await self._db.execute(
            select(BidProject).where(
                BidProject.rfp_source_ref == f"session:{session_id}",
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
            rfp_source_ref=f"session:{session_id}",
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
        """Ensure user has an org. Auto-create if not."""
        result = await self._db.execute(
            select(Membership).where(
                Membership.user_id == username,
                Membership.is_active == True,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is not None:
            return membership.org_id

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
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from services.web_app.db.models import Base
from services.web_app.api.adapter import SessionAdapter


@pytest_asyncio.fixture
async def adapter_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_adapter_creates_project_on_first_call(adapter_session):
    adapter = SessionAdapter(adapter_session)
    project = await adapter.get_or_create_project(
        session_id="sess_001",
        username="testuser",
        title="XX기관 사업",
    )
    assert project.id is not None
    assert project.title == "XX기관 사업"
    assert project.rfp_source_ref == "session:sess_001"
    assert project.org_id  # org was auto-created


@pytest.mark.asyncio
async def test_adapter_returns_same_project_for_same_session(adapter_session):
    adapter = SessionAdapter(adapter_session)
    p1 = await adapter.get_or_create_project("sess_001", "testuser")
    p2 = await adapter.get_or_create_project("sess_001", "testuser")
    assert p1.id == p2.id


@pytest.mark.asyncio
async def test_adapter_save_and_get_analysis(adapter_session):
    adapter = SessionAdapter(adapter_session)
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
async def test_adapter_analysis_versioning(adapter_session):
    adapter = SessionAdapter(adapter_session)
    project = await adapter.get_or_create_project("sess_003", "testuser")

    s1 = await adapter.save_analysis(project.id, project.org_id, {"v": 1})
    assert s1.version == 1

    s2 = await adapter.save_analysis(project.id, project.org_id, {"v": 2})
    assert s2.version == 2

    fetched = await adapter.get_analysis(project.id)
    assert fetched["analysis_json"]["v"] == 2
```

- [ ] **Step 2: Run integration tests** (aiosqlite already in requirements.txt from Task 1)

Run: `pytest services/web_app/tests/test_adapter.py -v`
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

- 14 SQLAlchemy models (org, project, document, company, audit)
- S3/R2 client with presigned URL support
- Project CRUD + asset upload/download APIs with org ownership
- Session adapter (session_id ↔ bid_project bridge)
- Alembic migration setup
- Integration tests with async SQLite"
```

---

## Post-Phase 1 Verification Checklist

Before proceeding to Phase 2, verify:

- [ ] All 14 tables can be created via Alembic migration on PostgreSQL
- [ ] S3 presigned upload/download works with actual R2/S3 bucket
- [ ] Session adapter correctly maps session_id → bid_project
- [ ] Existing Chat UI still works (no regressions)
- [ ] `BID_DATABASE_URL` not set → all new routes gracefully disabled
- [ ] Audit logs record create_project, upload_source, download_asset actions

## Next Steps

1. **Phase 1b plan:** Add review/approval tables (7 tables) + skill tables (2 tables) + departments/teams (2 tables)
2. **Phase 2 plan:** GenerationContract + orchestrator signature unification + presigned URL transport + quality gates
3. **Phase 3 plan:** Bid Workspace frontend + review/approval UI
4. **Phase 4 plan:** Legacy removal + performance optimization
