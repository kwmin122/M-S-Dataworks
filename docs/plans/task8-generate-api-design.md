# Task 8: `/api/projects/{id}/generate` Endpoint — Mini Design

**Date**: 2026-03-15
**Status**: Design for Review
**Context**: Phase 2 Contract Pipeline, Task 8 of 11

---

## Goal

Unified document generation API endpoint that:
1. Validates org + project access
2. Builds GenerationContract from DB data
3. Orchestrates rag_engine `/api/generate-document` call
4. Records DocumentRun lifecycle + DocumentRevision
5. Handles S3 asset pre-allocation + presigned URLs
6. Manages failure recovery (cleanup vs orphan handling)

---

## Critical Decisions (Must Lock Down)

### 1. Router Location

**Decision**: Extract to separate router module.

```
services/web_app/api/generate.py (NEW)
  ↓
services/web_app/main.py (include_router)
```

**Rationale**:
- `main.py` is already 2800+ lines
- Task 8 endpoint + helpers will add ~300 lines
- Separation improves testability (can mock DB without full app)
- Future: other endpoints (list runs, get revision) go in same router

**Not doing**: Inline in `main.py` (bloat, low cohesion)

---

### 2. Transaction Boundaries

**Decision**: Three-phase with SAME session + multiple commits + refresh pattern.

**Session Strategy**: **Reuse request-scoped session (Depends injection)**
- FastAPI's `Depends(get_async_session)` provides ONE session per request
- Multiple `await db.commit()` calls in same session = normal SQLAlchemy pattern
- Engine configured with `expire_on_commit=False` → ORM instances stay attached after commit
- `await db.refresh(obj)` optional (use only if need to reload from DB, not for re-attachment)
- **No new session creation needed** (avoids engine.py modification)

**Phase 1: Pre-execution**
```python
@router.post("/projects/{project_id}/generate")
async def generate_document(
    project_id: str,
    request: GenerateDocumentProjectRequest,
    user: CurrentUser = Depends(resolve_org_membership),
    db: AsyncSession = Depends(get_async_session),  # ← SAME session for all phases
):
    # 1. ACL check: require_project_access(project_id, "editor", user, db)
    #    - Verifies project exists + belongs to user's org → 404 if not
    #    - Org owner/admin → bypass (full access)
    #    - Others → require ProjectAccess row with level >= "editor"
    #    - Returns ProjectAccess or None (org bypass)
    # 2. Load contract data (CompanyProfile, etc.)
    # 3. Create DocumentRun (status=queued)
    # 4. Pre-create DocumentAssets (upload_status=presigned_issued)
    # 5. await db.commit() → run.id + asset.id persisted
    # 6. Keep run, asset_ids in memory (ORM instances still attached due to expire_on_commit=False)
```
**Outcome**: DocumentRun persisted, run ORM instance still attached (no refresh needed immediately).

**Phase 2: Transition to running + rag_engine call**
```python
    # 7. start_document_run(db=db, run=run)
    #    - run.status = "running"
    #    - run.started_at = now()
    #    (no refresh needed, expire_on_commit=False keeps ORM attached)
    # 8. await db.commit()

    # 10. Generate S3 presigned URLs (no DB, uses asset_ids from Phase 1)
    # 11. Call rag_engine /api/generate-document (timeout 300s)
    #     - On success → Phase 3A
    #     - On failure → Phase 3B
```

**Phase 3A: Success path**
```python
    # 9. complete_document_run(
    #        db=db, run=run,
    #        content_json, content_schema, output_files
    #    )
    #    - run.status = "completed"
    #    - create DocumentRevision
    #    - link assets (by asset_ids) to revision (upload_status → uploaded)
    #    - call _verify_output_assets (S3 head → verified)
    #    (no refresh needed, ORM still attached)
    # 10. await db.commit()
```

**Phase 3B: Failure path**
```python
    # 9. fail_document_run(db=db, run=run, error=str(exception))
    #    - run.status = "failed"
    #    - run.error_message = ...
    #    (no refresh needed, ORM still attached)
    # 10. Mark assets (by asset_ids from Phase 1) as failed:
    #     UPDATE document_assets SET upload_status='failed'
    #     WHERE id IN asset_ids
    # 11. await db.commit()
```

**Rationale**:
- **Same session reuse**: Standard SQLAlchemy pattern, multiple commits in one session OK
- **expire_on_commit=False**: ORM instances stay attached after commit (no refresh needed)
- **In-memory asset_ids**: DocumentAsset has no run_id FK, must track in endpoint scope
- **running transition**: Visibility during long generation (300s), enables stale run detection
- **Explicit asset IDs**: Prevents concurrent requests from marking each other's assets
- **No engine.py changes**: Uses existing public API (Depends), avoids exposing private factory

**Not doing**:
- Create new sessions for each phase (unnecessary complexity)
- Query by run_id after each commit (wasteful, have ORM instance already)
- Query assets by revision_id in failure path (revision doesn't exist yet)
- Add run_id FK to DocumentAsset (out of scope, requires migration)

---

### 3. Asset Lifecycle

**Decision**: State machine with explicit failed terminal state + in-memory ID tracking.

```
presigned_issued → uploading → uploaded → verified
       ↓ (rag_engine fail)
     failed
```

**Transitions**:
1. **Pre-create**: `DocumentAsset(upload_status="presigned_issued")` + flush → get asset.id
2. **Presigned URL issued**: Client/rag_engine receives `{asset_id, presigned_url, asset_type}`
3. **rag_engine success**: Contract adapter uploads → `output_files=[{asset_id, size_bytes, content_hash}]`
4. **complete_document_run**: Links assets to revision, transitions to `uploaded`
5. **_verify_output_assets**: S3 head_object → ETag → transitions to `verified`
6. **rag_engine failure**: Mark assets (by asset_ids) as `failed`

**Orphan Handling (CRITICAL: In-Memory Tracking)**:
- **Problem**: `DocumentAsset` has NO `run_id` foreign key
- **Problem**: At Phase 3B (failure), no `revision_id` exists yet
- **Problem**: Cannot safely query "this run's assets" from DB alone
- **Solution**: Keep `asset_ids: list[str]` in endpoint function scope (Phase 1 → Phase 3B)

**Failure Cleanup Pattern**:
```python
# Phase 1: Capture IDs
asset_ids = []
for doc_type in ["docx", "xlsx", "pptx"]:  # depending on doc_type
    asset = DocumentAsset(upload_status="presigned_issued", ...)
    db.add(asset)
    await db.flush()
    asset_ids.append(asset.id)  # CRITICAL: keep in memory

# Phase 3B: Use captured IDs
from sqlalchemy import update
await db.execute(
    update(DocumentAsset)
    .where(DocumentAsset.id.in_(asset_ids))  # Exact match, no query ambiguity
    .values(upload_status="failed")
)
```

**Why In-Memory**:
- Prevents race condition: concurrent generate requests won't mark each other's assets
- Explicit scope: only assets created in THIS request are affected
- No schema change: avoids adding `run_id` FK (out of Task 8 scope)

**Rationale**:
- Explicit failed state vs NULL/orphan is clearer audit trail
- Future background job can clean up old failed assets (soft delete: is_deleted=true)
- Presigned URLs expire in 1 hour anyway, so stale presigned_issued = effectively failed

**Not doing**:
- Delete assets on failure (lose audit trail)
- Query by revision_id (doesn't exist in failure path)
- Add run_id FK to DocumentAsset (requires migration, out of scope)
- Query by created_at range (unsafe with concurrent requests)

---

### 4. API Contract

**Decision**: Accept optional `analysis_snapshot_id`, fallback to `project.active_analysis_snapshot_id`.

**Request Model**:
```python
class GenerateDocumentProjectRequest(BaseModel):
    doc_type: str = Field(pattern="^(proposal|execution_plan|presentation|track_record)$")
    analysis_snapshot_id: str | None = None  # Optional
    params: dict = Field(default_factory=dict)  # doc_type-specific params
```

**RFP Source Resolution**:
```python
if request.analysis_snapshot_id:
    snapshot = await session.get(AnalysisSnapshot, request.analysis_snapshot_id)
    if not snapshot or snapshot.project_id != project_id:
        raise HTTPException(404, "Snapshot not found or not in this project")
    rfx_result = snapshot.analysis_json  # ACTUAL FIELD NAME
else:
    # Fallback: use project's active analysis
    if not project.active_analysis_snapshot_id:
        raise HTTPException(400, "No analysis snapshot. Analyze RFP first.")
    snapshot = await session.get(AnalysisSnapshot, project.active_analysis_snapshot_id)
    rfx_result = snapshot.analysis_json  # ACTUAL FIELD NAME
```

**Response Model**:
```python
class GenerateDocumentProjectResponse(BaseModel):
    run_id: str
    revision_id: str
    doc_type: str
    status: str  # "completed"
    output_files: list[OutputFileMetadata]
    generation_time_sec: float
    quality_report: dict | None

class OutputFileMetadata(BaseModel):
    asset_id: str
    asset_type: str  # docx, xlsx, pptx, png
    size_bytes: int
    download_url: str  # GET /api/assets/{asset_id}/download
```

**Rationale**:
- **Optional snapshot_id**: Supports both "regenerate with same RFP" and "use current active RFP"
- **Fallback to active**: Most common case is "generate from latest analysis"
- **Validation**: Ensures snapshot belongs to this project (prevent IDOR)
- **rfx_result from DB**: Single source of truth (no re-analysis in generate)

**Not doing**:
- Accept raw rfx_dict in request (bypass analysis persistence, lose audit trail)
- Always require analysis_snapshot_id (forces extra lookup for common case)
- Return presigned upload URLs (rag_engine handles upload, client only downloads)

---

## Overall Flow

```
POST /api/projects/{project_id}/generate
  ↓
[Phase 1: Pre-execution - db session from Depends]
1. ACL check: require_project_access(project_id, "editor", user, db)
   - Verifies org + ProjectAccess row + anti-enumeration (404 on deny)
2. Load project, snapshot (analysis_json), company profile
3. Build GenerationContract (contract_builder.build_generation_contract)
4. Create DocumentRun (status=queued)
5. Pre-create DocumentAssets (upload_status=presigned_issued)
6. await db.commit() → capture run_id, asset_ids in memory
  ↓
[Phase 2: Transition to running + rag_engine call]
7. start_document_run(db, run) → status=running (ORM still attached, no refresh needed)
8. await db.commit()
9. Generate S3 presigned URLs (s3.generate_presigned_upload_url)
10. Call rag_engine /api/generate-document (timeout 300s)
    {doc_type, rfx_result, contract, params, upload_targets}
  ↓
[Phase 3A: Success path]
11. complete_document_run(db, run, content_json, ..., output_files)
    - status=completed
    - create DocumentRevision
    - link assets (WHERE id IN asset_ids) to revision
    - _verify_output_assets (S3 head → verified)
    (ORM still attached, no refresh needed)
12. await db.commit()
13. Return 200 {run_id, revision_id, output_files, download_urls}

[Phase 3B: Failure path - rag_engine error]
11. fail_document_run(db, run, error=str(exception))
12. Mark assets failed: UPDATE WHERE id IN asset_ids SET upload_status='failed'
13. await db.commit()
14. Raise HTTPException 502 Bad Gateway (upstream rag_engine failure)
    OR HTTPException 504 Gateway Timeout (rag_engine timeout)
```

---

## File Structure

**New**:
- `services/web_app/api/generate.py` (~300 lines)
  - `router = APIRouter(prefix="/api")`
  - `POST /projects/{project_id}/generate`
  - Helper: `_load_contract_data(session, org_id, project_id)`
  - Helper: `_create_presigned_upload_targets(session, org_id, project_id, doc_type)`
  - Helper: `_call_rag_engine_generate(contract, rfx_result, params, upload_targets)`

**Modified**:
- `services/web_app/main.py`
  - `from services.web_app.api.generate import router as generate_router`
  - `app.include_router(generate_router)`

---

## Error Cases

| Scenario | HTTP Status | DocumentRun.status | Asset.upload_status | Rationale |
|----------|-------------|-------------------|---------------------|-----------|
| Project not found | 404 | N/A | N/A | Client error (bad project_id) |
| No analysis snapshot | 400 | N/A | N/A | Client error (must analyze RFP first) |
| Snapshot not in project | 404 | N/A | N/A | Client error (IDOR or wrong snapshot_id) |
| rag_engine timeout (>300s) | **504 Gateway Timeout** | failed | failed | **Upstream timeout, not internal bug** |
| rag_engine returns error | **502 Bad Gateway** | failed | failed | **Upstream failure, not internal bug** |
| DB commit failure (Phase 3A) | 500 Internal Server Error | running (stale) | uploaded (stale) | **Internal DB issue** |
| Contract build failure | 500 Internal Server Error | N/A | N/A | **Internal logic error** |

**Error Code Semantics**:
- **4xx**: Client error (bad request, not found, access denied)
- **500**: Internal server error (web_app bug, DB failure, code error)
- **502**: Upstream service (rag_engine) returned error response
- **504**: Upstream service (rag_engine) timed out

This distinction helps monitoring/alerting:
- 500 → page web_app oncall (our bug)
- 502/504 → page rag_engine oncall (their bug)

**Stale state recovery**: Future background job can detect `status=running AND completed_at IS NULL AND created_at < now() - 1 hour` → mark as failed.

---

## Security

- **ACL**: `require_project_access(project_id, "editor", user, db)` (enforces org + ProjectAccess row + anti-enumeration)
  - Org owner/admin: bypass project_access check (full access)
  - Other users: require ProjectAccess row with level >= "editor"
  - Unauthorized: 404 (not 403, prevents IDOR enumeration)
- **IDOR**: Snapshot must belong to project (`snapshot.project_id == project_id`)
- **Input validation**: Pydantic models with Field constraints
- **S3 presigned URLs**: Expire in 3600s, scoped to org prefix

---

## Dependencies

**Already implemented** (verified):
- `generation_service.py`: create_document_run, start_document_run, complete_document_run, fail_document_run ✓
- `contract_builder.py`: build_generation_contract ✓
- `rag_engine /api/generate-document`: Unified endpoint ✓
- `storage/s3.py`: `generate_presigned_upload_url(key, expires_in=3600)` ✓
- `db/models/project.py`: `BidProject.active_analysis_snapshot_id` ✓
- `api/deps.py`: `CurrentUser.org_id`, `Depends(resolve_org_membership)` ✓

---

## Testing Strategy

**Unit tests** (`tests/web_app/api/test_generate.py`):
1. Happy path: project exists, snapshot exists, user has access → 200 + revision_id
2. Project not found → 404
3. User lacks project access (not editor) → 404
4. No snapshot → 400
5. Snapshot IDOR (wrong project) → 404
6. rag_engine returns error → **502 Bad Gateway** + DocumentRun.status=failed
7. rag_engine timeout → **504 Gateway Timeout** + assets marked failed

**Integration test** (requires PostgreSQL + S3 mock):
1. Full flow: create project → analyze → generate → verify assets linked to revision
2. Failure recovery: rag_engine fails → verify assets marked failed, run marked failed

**Deferred to Task 11**:
- Full regression with all doc_types
- Performance test (10 concurrent generates)

---

## Verified Dependencies (All Questions Closed)

1. **S3 client method**: ✅ CONFIRMED
   - `storage/s3.py:51` has `generate_presigned_upload_url(key, expires_in=3600)`
   - Signature matches requirements

2. **Active snapshot field**: ✅ CONFIRMED
   - `db/models/project.py:34` `BidProject.active_analysis_snapshot_id: Mapped[str | None]`
   - Fallback pattern supported

3. **Session/ACL pattern**: ✅ CONFIRMED
   - `api/deps.py:20` `CurrentUser` has `org_id: str` field
   - Pattern: `Depends(resolve_org_membership)` for ACL
   - Existing routers use this pattern (see `api/projects.py`)

4. **CompanyProfile model**: ✅ CONFIRMED
   - `db/models/company.py:16` `class CompanyProfile` exists
   - Structure compatible with `contract_builder.build_generation_contract`

5. **AnalysisSnapshot field**: ✅ CONFIRMED (CRITICAL FIX)
   - Field is `analysis_json`, NOT `rfp_summary_json`
   - `db/models/project.py:114` `analysis_json: Mapped[dict]`

6. **Session strategy**: ✅ FINALIZED
   - `db/engine.py:57` `get_async_session()` is FastAPI Depends generator
   - `db/engine.py:39` `expire_on_commit=False` → ORM stays attached after commit
   - **Design decision**: Reuse same request-scoped session (no manual factory needed)

---

## Approval Checklist

Before implementation:
- [ ] Review 4 critical decisions (router, transactions, asset lifecycle, API contract)
- [ ] Verify dependencies exist (S3 client, active_snapshot_id, session format)
- [ ] Answer open questions
- [ ] Confirm testing strategy
- [ ] Proceed to implementation

---

**Estimated implementation time**: 2-3 hours (assuming dependencies exist)
**Estimated testing time**: 1-2 hours (unit + integration)
**Risk level**: Medium (multiple DB transactions, external call, state management)
