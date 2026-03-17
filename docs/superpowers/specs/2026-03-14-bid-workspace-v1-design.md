# Kira Bot v1.0 — Bid Workspace Design Spec

**Status**: Canonical (Locked)
**Date**: 2026-03-14
**Approach**: B+ (Modular Monolith + DB-centric bid_project + org-scoped assets)

---

## 1. One-Line Definition

Kira 내부 확장형 Bid Workspace. bid_project DB 중심, org-scoped object storage, session은 thin adapter로 축소, proposal path부터 pack/skill interface 주입, ACL/approval/audit는 DB 중심.

---

## 2. Foundational Principles

1. **상태와 권한의 진실 = DB**. 파일시스템도 세션 메모리도 아님.
2. **org_id가 유일한 tenant key**. company_id, session_id는 1급 키가 아님.
3. **생성은 비동기 document_run 기준으로 처리한다.** Run이 생성/실행/완료/실패의 lifecycle을 가짐.
4. **document_assets는 업로드 상태를 가진다.** presigned URL 발급 → 업로드 중 → 업로드 완료 → 검증 완료.
5. **JSON 본문/분석/품질 리포트는 모두 schema version을 가진다.** content_schema, analysis_schema, quality_schema 필드로 버전 추적.
6. **파일은 object storage(S3/R2)에, 메타데이터와 소유권은 DB에.**
7. **rag_engine = stateless compute**. DB 접근 없음, 파일시스템 접근 없음 (Layer 1 KnowledgeDB 읽기 전용 번들 제외).
8. **PostgreSQL 즉시**. SQLite 경유 없음.
9. **오케스트레이터 통합이 목표가 아니라 문서 타입 간 계약 통일이 목표.**

---

## 3. v1 Tenant Assumption (Locked)

```
One organization = one bidding legal entity

- org_id가 유일한 tenant key
- 한 org 안에서 복수 법인/계열사/컨소시엄 주체를 구분하지 않음
- company_profiles는 org당 1개 (UNIQUE)
- 이 가정을 깨야 하는 시점:
    "한 조직이 여러 입찰 주체로 참여"하는 요구
- 그때의 확장 경로:
    bid_entities 테이블 추가
    bid_projects.entity_id FK 추가
    company_profiles → entity_id로 재연결
- v1에서는 이 확장을 구현하지 않음
```

---

## 4. doc_type Enum (Single Dictionary, All Layers)

```
proposal         기술제안서
execution_plan   수행계획서/WBS
presentation     PPT 발표자료
track_record     실적/경력 기술서
checklist        제출서류 체크리스트
```

Applies to: DB CHECK constraints, Python enum, TypeScript union, API parameters.

Removed/merged:
- `technical_proposal` → `proposal`
- `wbs` → `execution_plan`
- `ppt` → `presentation`

---

## 5. Data Model (20 Tables + 3 Company Tables)

### 5.1 Organization / Access Layer

#### organizations
| Column | Type | Notes |
|--------|------|-------|
| id | PK | cuid2 |
| name | TEXT NOT NULL | |
| plan_tier | TEXT | free/pro/enterprise |
| settings_json | JSONB | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

Role: Self-serve SaaS tenant boundary. Top-level owner of all data.

#### departments
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| name | TEXT NOT NULL | |
| created_at | TIMESTAMPTZ | |

#### teams
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| department_id | FK → departments | nullable |
| name | TEXT NOT NULL | |
| created_at | TIMESTAMPTZ | |

#### memberships
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| user_id | FK → existing auth users | **No separate users table. Reuse existing Kira auth/user.** |
| department_id | FK → departments | nullable |
| team_id | FK → teams | nullable |
| role | TEXT | owner / admin / editor / reviewer / approver / viewer |
| is_active | BOOLEAN | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### project_access
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| project_id | FK → bid_projects | |
| user_id | FK | nullable (user-level access) |
| team_id | FK → teams | nullable (team-level access) |
| access_level | TEXT | owner / editor / reviewer / approver / viewer |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

Role: Project-scoped ACL. Without this, org editors see all projects. This enables dept/team/document-level control.

#### approval_lines
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| doc_type | TEXT | CHECK against doc_type enum |
| name | TEXT | |
| is_active | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

#### approval_line_steps
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| approval_line_id | FK → approval_lines | |
| step_order | INT | |
| approver_user_id | FK | nullable (specific user) |
| approver_role | TEXT | nullable (role-based) |
| team_id | FK → teams | nullable (team-based) |
| required_decision_count | INT | default 1. When approver_role or team_id is set, this specifies how many matching users must record 'approved' in approval_records before the step is satisfied. |
| created_at | TIMESTAMPTZ | |

Split into 2 tables because approval line definition and actual approval execution must be separated.

### 5.2 Bid Project Layer

#### bid_projects
| Column | Type | Notes |
|--------|------|-------|
| id | PK | cuid2 |
| org_id | FK → organizations | tenant key |
| created_by | FK → users | |
| title | TEXT NOT NULL | |
| status | TEXT | draft / collecting_inputs / analyzing / ready_for_generation / generating / in_review / changes_requested / approved / locked_for_submission / submitted / archived |
| rfp_source_type | TEXT | upload / nara_search / manual |
| rfp_source_ref | TEXT | nullable (나라장터 공고번호 등) |
| active_analysis_snapshot_id | FK → analysis_snapshots | nullable, **DEFERRABLE INITIALLY DEFERRED** (circular FK with analysis_snapshots.project_id) |
| generation_mode | TEXT | strict_template / starter / upgrade |
| settings_json | JSONB | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

**company_id is NOT in this table.** Tenant key is org_id only.

**Circular FK resolution**: `bid_projects.active_analysis_snapshot_id` → `analysis_snapshots` is `DEFERRABLE INITIALLY DEFERRED`. Insert order: (1) INSERT bid_project with `active_analysis_snapshot_id = NULL`, (2) INSERT analysis_snapshot with `project_id`, (3) UPDATE bid_project SET `active_analysis_snapshot_id`. All within a single transaction.

#### source_documents
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| project_id | FK → bid_projects | nullable |
| document_kind | TEXT | rfp / company_profile / template / past_proposal / track_record / personnel / supporting_material / final_upload |
| uploaded_by | FK → users | |
| asset_id | FK → document_assets | **storage_uri source of truth is document_assets ONLY** |
| parse_status | TEXT | pending / parsing / completed / failed |
| parse_result_json | JSONB | |
| created_at | TIMESTAMPTZ | |

**No storage_uri column here.** URI lives only in document_assets. source_documents references via asset_id FK.

#### analysis_snapshots
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| project_id | FK → bid_projects | |
| version | INT | increments on re-analysis |
| analysis_json | JSONB NOT NULL | **canonical source, immutable** |
| analysis_schema | TEXT | e.g. "rfx_analysis_v1" |
| summary_md | TEXT | 3-section markdown (denormalized for display) |
| go_nogo_result_json | JSONB | |
| is_active | BOOLEAN | **partial unique index: (project_id) WHERE is_active = true** |
| created_by | FK → users | nullable |
| created_at | TIMESTAMPTZ | |

Principle: Immutable snapshot. analysis_json is the single canonical source. Scalar columns (summary_md) are denormalized for convenience only. Only one active snapshot per project (enforced by partial unique index).

### 5.3 Document Generation / Version / Asset Layer

#### document_runs
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| project_id | FK → bid_projects | |
| analysis_snapshot_id | FK → analysis_snapshots | which analysis produced this |
| doc_type | TEXT | CHECK against doc_type enum |
| status | TEXT | queued / running / completed / failed / superseded |
| params_json | JSONB | total_pages, methodology, duration_min, etc. |
| engine_version | TEXT | rag_engine version tag |
| mode_used | TEXT | strict_template / starter / upgrade |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |
| error_message | TEXT | |
| created_by | FK → users | |
| created_at | TIMESTAMPTZ | |

**Generation is asynchronous, keyed by document_run.** Run has a lifecycle: queued → running → completed/failed.

#### document_revisions
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| project_id | FK → bid_projects | |
| doc_type | TEXT | denormalized |
| run_id | FK → document_runs | nullable (user edits have no run) |
| derived_from_revision_id | FK → document_revisions | nullable (lineage tracking) |
| revision_number | INT | |
| source | TEXT | ai_generated / user_edited / reassembled / imported_final |
| status | TEXT | draft / review_requested / in_review / changes_requested / approved / locked / submitted |
| title | TEXT | |
| content_json | JSONB | **universal document body (not proposal-specific)** |
| content_schema | TEXT | "proposal_sections_v1" / "execution_plan_tasks_v1" / "presentation_slides_v1" / "track_record_v1" / "checklist_v1" |
| quality_report_json | JSONB | |
| quality_schema | TEXT | e.g. "quality_report_v1" |
| upgrade_report_json | JSONB | |
| created_by | FK → users | |
| created_at | TIMESTAMPTZ | |

**content_json is the universal document body.** Each doc_type has its own content_schema. See section 5.6 for schema definitions.

#### document_assets
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | ownership verification path |
| project_id | FK → bid_projects | nullable (source docs may not have project) |
| revision_id | FK → document_revisions | nullable (source docs have no revision) |
| asset_type | TEXT | docx / hwpx / xlsx / pptx / pdf / png / json / original |
| storage_uri | TEXT NOT NULL | **sole source of truth for physical location** e.g. "s3://kira-assets/orgs/{oid}/projects/{pid}/assets/{aid}/{hash}.docx" |
| upload_status | TEXT | presigned_issued / uploading / uploaded / verified / failed |
| original_filename | TEXT | |
| mime_type | TEXT | |
| size_bytes | BIGINT | |
| content_hash | TEXT | sha256 |
| is_deleted | BOOLEAN | soft delete |
| created_at | TIMESTAMPTZ | |

**upload_status lifecycle**: presigned_issued → uploading → uploaded → verified (hash check) → or failed.

#### project_current_documents
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | tenant scoping |
| project_id | FK → bid_projects | |
| doc_type | TEXT | **UNIQUE(project_id, doc_type)** |
| current_revision_id | FK → document_revisions | |
| updated_at | TIMESTAMPTZ | |

Role: Fast "current version" pointer. Separate table instead of multiple FK columns on bid_projects.

### 5.4 Review / Approval Layer

#### review_requests
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| project_id | FK → bid_projects | |
| revision_id | FK → document_revisions | |
| approval_line_id | FK → approval_lines | |
| requested_by | FK → users | |
| status | TEXT | pending / in_review / approved / rejected / cancelled |
| comment_md | TEXT | |
| created_at | TIMESTAMPTZ | |
| resolved_at | TIMESTAMPTZ | |

#### review_comments
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| review_request_id | FK → review_requests | |
| revision_id | FK → document_revisions | |
| author_id | FK → users | |
| comment_md | TEXT | |
| anchor_json | JSONB | section/paragraph/whole-document anchor |
| created_at | TIMESTAMPTZ | |

#### approval_records
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| review_request_id | FK → review_requests | |
| approval_line_step_id | FK → approval_line_steps | |
| approver_id | FK → users | |
| step_order | INT | |
| decision | TEXT | approved / rejected / returned |
| comment_md | TEXT | |
| decided_at | TIMESTAMPTZ | |

### 5.5 Learning / Skill Layer

#### skill_update_candidates
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| project_id | FK → bid_projects | nullable |
| doc_type | TEXT | |
| source_revision_id | FK → document_revisions | nullable |
| pattern_key | TEXT | diff_tracker hash |
| pattern_json | JSONB | |
| occurrence_count | INT | |
| status | TEXT | detected / pending_review / approved / rejected / applied / rolled_back |
| approved_by | FK → users | nullable |
| created_at | TIMESTAMPTZ | |
| applied_at | TIMESTAMPTZ | |

#### skill_versions
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| doc_type | TEXT | |
| version | INT | |
| content_json | JSONB | |
| status | TEXT | active / shadow / archived / rolled_back |
| promoted_by | FK → users | nullable |
| created_at | TIMESTAMPTZ | |

Separation: Candidates (detected patterns) vs versions (promoted, active skills).

### 5.6 Audit Layer

#### audit_logs
| Column | Type | Notes |
|--------|------|-------|
| id | PK BIGSERIAL | |
| org_id | FK → organizations | |
| user_id | FK → users | nullable (system actions) |
| project_id | FK → bid_projects | nullable |
| action | TEXT | create_project / upload_source / run_analysis / generate_document / edit_revision / request_review / approve / reject / download_asset / upload_final / approve_skill_update / rollback_skill / archive_project / ... |
| target_type | TEXT | bid_project / document_revision / document_asset / ... |
| target_id | TEXT | |
| detail_json | JSONB | before/after summary |
| ip_address | INET | |
| user_agent | TEXT | |
| created_at | TIMESTAMPTZ | |

**Append-only. UPDATE/DELETE prohibited.**

Recommended indexes:
- `(org_id, created_at DESC)`
- `(project_id, created_at DESC)`
- `(target_type, target_id)`

### 5.7 Company Data (org-scoped relational, replacing CompanyDB)

#### company_profiles
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | **UNIQUE** (one per org in v1) |
| company_name | TEXT | |
| business_type | TEXT | |
| business_number | TEXT | |
| capital | TEXT | |
| headcount | INT | |
| licenses | JSONB | |
| certifications | JSONB | |
| writing_style | JSONB | analyze_company_style() result |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### company_track_records
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| project_name | TEXT | |
| client_name | TEXT | |
| contract_amount | BIGINT | |
| period_start | DATE | |
| period_end | DATE | |
| description | TEXT | |
| technologies | JSONB | |
| embedding | VECTOR(1536) | pgvector |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### company_personnel
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| org_id | FK → organizations | |
| name | TEXT | |
| role | TEXT | |
| years_experience | INT | |
| certifications | JSONB | |
| skills | JSONB | |
| description | TEXT | |
| embedding | VECTOR(1536) | pgvector |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

Semantic search via pgvector cosine similarity. Sufficient for hundreds~thousands of records per org.

### 5.8 content_json Schema Definitions

```jsonc
// content_schema = "proposal_sections_v1"
{
  "sections": [
    {"name": "사업 이해도", "text": "...", "weight": 0.15, "page_budget": 8}
  ]
}

// content_schema = "execution_plan_tasks_v1"
{
  "tasks": [
    {"id": "T1", "name": "요구분석", "phase": "분석",
     "start_month": 1, "end_month": 2, "assignee": "PM"}
  ],
  "methodology": "waterfall",
  "total_months": 12
}

// content_schema = "presentation_slides_v1"
{
  "slides": [
    {"slide_number": 1, "type": "cover", "title": "...", "body": "...",
     "speaker_notes": "..."}
  ],
  "qna_pairs": [
    {"question": "...", "answer": "...", "category": "기술"}
  ],
  "total_duration_min": 30
}

// content_schema = "track_record_v1"
{
  "records": [
    {"project_name": "...", "description": "...", "relevance_score": 0.85}
  ],
  "personnel": [
    {"name": "...", "role": "...", "match_reason": "..."}
  ]
}

// content_schema = "checklist_v1"
{
  "items": [
    {"category": "필수서류", "item": "사업자등록증", "required": true, "note": "..."}
  ]
}
```

---

## 6. Asset Storage Architecture

### Object Storage First (S3/R2 from Day 1)

```
s3://{bucket}/
└── orgs/{org_id}/
    ├── sources/{source_doc_id}/{content_hash}.{ext}
    └── projects/{project_id}/
        └── assets/{asset_id}/{content_hash}.{ext}
```

- **Railway**: Cloudflare R2 (egress-free) or AWS S3 external connection.
- **No local filesystem storage for production assets.**
- document_assets.storage_uri is the sole source of truth for physical location.
- source_documents has NO storage_uri column; references document_assets via asset_id FK.

### Download Flow

```
GET /api/assets/{asset_id}/download
  → Extract user_id from session
  → DB: document_assets WHERE id = {asset_id}
  → DB: memberships WHERE user_id AND org_id == asset.org_id
  → project_access check (viewer or above)
  → Pass → generate presigned download URL (or stream from S3)
  → audit_logs INSERT (download_asset)
```

### Upload Flow

```
POST /api/projects/{project_id}/sources
  → org ownership verification
  → DB INSERT: document_assets (upload_status = presigned_issued)
  → Generate presigned upload URL
  → Return {asset_id, presigned_url} to client
  → Client uploads directly to S3
  → Webhook/poll: upload_status → uploaded → verified (hash check)
  → DB INSERT: source_documents (asset_id FK)
  → Async: parser execution → parse_status = completed
  → audit_logs INSERT (upload_source)
```

### upload_status Lifecycle

```
presigned_issued → uploading → uploaded → verified → (ready)
                       │              │
                       └→ failed      └→ failed (hash mismatch)
```

### Legacy Download Adapter

```
GET /api/proposal/download/{filename}?project_id={pid}&revision_id={rid}
  (DEPRECATED — Phase 3 removal)
  → DB: document_assets
    WHERE original_filename = {filename}
    AND project_id = {pid}
    AND revision_id = {rid}
    AND org_id = current_user.org_id
  → Found: redirect to /api/assets/{asset_id}/download
  → Not found: 404

Filename-only identification is PROHIBITED. project_id + revision_id + org_id required.
```

---

## 7. API Boundaries

### Role Split

| Concern | Owner | Reason |
|---------|-------|--------|
| Auth/authz | web_app | DB owner, session mgmt |
| Project CRUD | web_app | DB owner |
| Asset ownership + serving | web_app | DB + S3 access |
| Approval/review flows | web_app | DB transactions |
| Audit logging | web_app | append-only DB |
| RFP analysis (LLM) | rag_engine | GPU/LLM resources |
| Document generation (LLM + assembly) | rag_engine | Pipeline logic |
| Parsing (HWP/PDF/DOCX) | rag_engine | Parser libraries |
| Layer 1/2 knowledge search | rag_engine | ChromaDB (read-only bundle) |

### web_app → rag_engine Transport Contract (Locked)

**Presigned Upload URL method. No alternatives.**

```
1. web_app sends generation request with presigned upload URLs:
   POST /api/generate-document
   Body: {
     doc_type: "proposal",
     analysis_json: {...},
     contract: GenerationContract,
     params: {...},
     upload_targets: [
       {asset_id: "ast_001", presigned_url: "https://r2.../put?sig=...",
        asset_type: "docx"},
       {asset_id: "ast_002", presigned_url: "https://r2.../put?sig=...",
        asset_type: "json"}
     ]
   }

2. rag_engine generates files, uploads directly to S3 via presigned URLs.

3. rag_engine returns metadata only:
   Response: {
     doc_type: "proposal",
     uploaded: [
       {asset_id: "ast_001", size_bytes: 45200, content_hash: "a1b2c3..."},
       {asset_id: "ast_002", size_bytes: 12800, content_hash: "d4e5f6..."}
     ],
     content_json: {...},
     content_schema: "proposal_sections_v1",
     quality_report: {...},
     quality_schema: "quality_report_v1",
     generation_time_sec: 32.5
   }

4. web_app records document_assets + document_revisions in DB.
```

Why: rag_engine uploads directly to S3 (no web_app bottleneck for large files). web_app controls presigned URL generation (security boundary). Response is pure JSON (simple parsing, clear error handling).

### rag_engine Input Contract

```
Analysis/Parsing:
  POST /api/parse-document
  Content-Type: multipart/form-data
  Body: file (binary stream)
  → web_app reads from S3, streams to rag_engine

Generation:
  POST /api/generate-document
  Content-Type: application/json
  Body: pure data (no file paths)
  → analysis_json, contract, params, upload_targets

Knowledge:
  POST /api/knowledge/search
  Body: {query, doc_type, top_k}

Quality:
  POST /api/quality-check
  Body: {content_json, content_schema, rules}
```

**rag_engine receives NO local file paths. Ever.**

### Key API Endpoints

#### Project Management (web_app)
```
POST   /api/projects                                    Create project
GET    /api/projects                                    List (org-scoped)
GET    /api/projects/{id}                               Detail
PATCH  /api/projects/{id}                               Update status/settings
DELETE /api/projects/{id}                               Archive (soft)

POST   /api/projects/{id}/sources                       Upload source doc
GET    /api/projects/{id}/sources                       List source docs

POST   /api/projects/{id}/analyze                       Run analysis → rag_engine
GET    /api/projects/{id}/analysis                      Active snapshot

POST   /api/projects/{id}/generate                      Generate doc → rag_engine
GET    /api/projects/{id}/documents                     List docs (filter by doc_type)
GET    /api/projects/{id}/documents/{doc_type}/current   Current revision
```

#### Document Versions (web_app)
```
GET    /api/revisions/{id}                              Revision detail + content_json
PUT    /api/revisions/{id}/sections                     Edit content
POST   /api/revisions/{id}/reassemble                   Reassemble output → rag_engine
```

#### Assets (web_app)
```
GET    /api/assets/{id}/download                        Ownership-verified download
```

#### Reviews (web_app)
```
POST   /api/revisions/{id}/review                       Request review
POST   /api/reviews/{id}/approve                        Approve
POST   /api/reviews/{id}/reject                         Reject
GET    /api/reviews/{id}/comments                       List comments
POST   /api/reviews/{id}/comments                       Add comment
```

#### rag_engine (stateless compute)
```
POST   /api/analyze-rfp                                 RFP analysis
POST   /api/generate-document                           Unified document generation
POST   /api/parse-document                              File parsing
POST   /api/knowledge/search                            Layer 1/2 search
POST   /api/quality-check                               Quality validation
```

---

## 8. Generation Contract (Document Type Interface Unification)

### Goal

Not orchestrator unification, but **contract unification across document types**.

All 4 document types (proposal, execution_plan, presentation, track_record) must consume the same interface.

### GenerationContract

```python
# Requires Python 3.10+ (or `from __future__ import annotations` for 3.9)

@dataclass
class GenerationContract:
    # 1. Company Context Contract
    company_context: CompanyContext
    company_profile_md: str | None
    writing_style: dict | None

    # 2. Skill Retrieval Contract
    knowledge_units: list[KnowledgeUnit]
    learned_patterns: list[dict]
    pack_config: PackConfig | None

    # 3. Mode Selection Contract
    mode: Literal["strict_template", "starter", "upgrade"]
    template_source: str | None

    # 4. Quality Contract
    quality_rules: QualityRules
    required_checks: list[str]
    pass_threshold: float

@dataclass
class CompanyContext:
    similar_projects: list[dict]
    matching_personnel: list[dict]
    licenses: list[str]
    certifications: list[str]
    profile_summary: str

@dataclass
class QualityRules:
    blind_words: list[str]
    custom_forbidden: list[str]
    min_section_length: int
    max_ambiguity_score: float

@dataclass
class GenerationResult:
    doc_type: str
    output_files: list[OutputFile]
    content_json: dict
    content_schema: str
    quality_report: dict | None
    quality_schema: str | None
    upgrade_report: dict | None       # G5 template compliance report
    metadata: dict
    generation_time_sec: float
```

### Current Compliance Matrix

| Contract | proposal | execution_plan | presentation | track_record |
|----------|----------|----------------|--------------|--------------|
| company_context | build_company_context() | build_company_context() | build_company_context() | CompanyDB direct |
| writing_style | profile.writing_style | profile.writing_style | profile.writing_style | not used |
| Layer 1 knowledge | KnowledgeDB search | KnowledgeDB search | not used | not used |
| Layer 2 patterns | auto_learner | auto_learner | auto_learner | not used |
| pack_config | not connected | use_pack=True | not connected | not connected |
| mode selection | none | none | none | none |
| quality_check | quality_checker | none | none | none |

### Phase 1 Target

Unify orchestrator signatures to accept GenerationContract. Inject pack interface into proposal path (section_writer.assemble_pack_prompt already exists).

---

## 9. Quality Gates

### 5 Gates

| # | Gate | Checks | Judge | DB Record |
|---|------|--------|-------|-----------|
| G1 | Document Quality | Blind violations, ambiguity, min length, section completeness, company name exposure | Auto (quality_checker) | document_revisions.quality_report_json |
| G2 | Operations | Generation success/failure, file integrity (hash), downloadable | Auto (document_runs.status) | document_runs.status + error_message |
| G3 | Security | org ownership, asset ACL, tenant isolation | Auto | audit_logs |
| G4 | Learning | Pattern occurrence >= threshold, approver review | Human (approver) | skill_update_candidates.status |
| G5 | Template | Mode compliance (strict=template-faithful, starter=basic structure) | Auto + Human | document_revisions.upgrade_report_json |

**Blind check (company name exposure) is in G1 (Document Quality), NOT G3 (Security).** Security gate covers ACL/IDOR/tenant isolation only.

### Gate Execution Timing

```
Document generation completed (document_runs.status = completed)
  → G1 auto: quality_checker → quality_report_json
  → G2 auto: file existence + hash verification
  → G3 auto: ownership scan
  → document_revisions.status = "draft" (all auto gates pass)

Review requested (review_requests INSERT)
  → G5 auto: mode compliance check
  → Human review → approved/rejected

Learning pattern detected (skill_update_candidates INSERT)
  → G4 human approval required
  → approved → skill_versions applied
```

### Gate Failure Behavior

```
G1 fail (blind violation):
  Revision created, but quality_report records violations.
  UI shows warning. Review request blocked if violations > 0.

G2 fail (generation failure):
  document_runs.status = "failed", error_message recorded.
  Retry possible (new run).

G3 fail (ownership violation):
  404 returned (existence not revealed).
  audit_logs records violation attempt.

G4 fail (learning rejected):
  skill_update_candidates.status = "rejected".
  Pattern preserved for future re-review.

G5 fail (template non-compliance):
  upgrade_report records differences.
  Reviewer shown diff summary.
```

---

## 10. Session → bid_project Migration Strategy

### Phase Plan

```
Phase 1: Storage Layer + ACL
├── PostgreSQL schema (23 tables)
├── S3/R2 asset storage
├── Download API with ownership verification
├── Session adapter: session_id ↔ bid_project.id mapping
├── Existing Chat UI works via adapter
└── audit_log recording starts

Phase 2: Contract Unification + Generation Pipeline
├── GenerationContract interface definition
├── 4 orchestrator signature unification
├── Proposal path pack branch addition
├── quality_check expansion to all doc types
├── document_runs/revisions/assets DB recording
├── analysis_snapshots persistence (memory → DB)
└── doc_type enum migration: rename "wbs"→"execution_plan", "ppt"→"presentation"
    in existing Python modules (wbs_*.py, ppt_*.py), frontend code, and API params.
    Use alias mapping during transition: accept old names, store new names.

Phase 3: Workspace UI + Review/Approval
├── Bid Workspace frontend (project list/detail)
├── Document editing UI (MarkdownEditor already exists)
├── Review request/approval/rejection UI
├── project_access permission UI
├── skill_update_candidates management UI
└── Session adapter marked DEPRECATED

Phase 4: Legacy Removal + Stabilization
├── Session adapter removal
├── SESSIONS dict removal
├── Unused API cleanup
├── Performance optimization (indexes, queries)
└── Load testing + security audit
```

### Data Migration

```
Current                                →  B+ Target
──────────────────────────────────────────────────────
SESSIONS[sid]                          →  bid_projects row
latest_rfx_analysis (memory)           →  analysis_snapshots row
data/proposals/*.docx                  →  S3 orgs/{oid}/projects/{pid}/assets/
data/proposals/*_sections.json         →  document_revisions.content_json
data/company_db/{cid}/profile.json     →  company_profiles row
data/company_db/{cid}/ ChromaDB        →  company_track_records + company_personnel (pgvector)
data/knowledge_db/                     →  kept (Layer 1 shared, rag_engine bundle)
learning_state.json                    →  skill_update_candidates + skill_versions
sessionStorage kira_session_id         →  kira_project_id (or adapter)
```

### Session Adapter Rules (Locked)

```
1. READ/WRITE-THROUGH ONLY
   Adapter internally calls bid_project API.
   No business logic in adapter itself.

2. NEW FEATURE ADDITION PROHIBITED
   New features go to /api/projects/* only.
   No new endpoints on adapter.

3. SOURCE OF TRUTH = Workspace API
   Data written via adapter lands in bid_project DB.
   Session memory is cache only, not canonical.

4. REMOVAL MILESTONE
   Phase 3 completion: marked DEPRECATED
   Phase 4: removal
   Pre-removal: adapter call volume monitoring → confirm 0 → remove
```

---

## 11. State Machine Rules & Cross-Table Coupling

### document_runs.status = "superseded"

A document_run transitions to `superseded` when a **new completed run** exists for the same `(project_id, doc_type)`. This is an **explicit transition** triggered when the new run completes successfully (status = completed). The previous completed run is marked superseded. Failed runs are not superseded (they stay failed).

### review_requests.status ↔ document_revisions.status Coupling

```
review_requests.status    →  document_revisions.status
──────────────────────────────────────────────────────
pending                   →  review_requested
in_review                 →  in_review
approved                  →  approved
rejected                  →  changes_requested
cancelled                 →  draft (reverted)
```

These transitions are **synchronous within a single transaction**. When `review_requests.status` changes, the corresponding `document_revisions.status` is updated in the same DB transaction.

### bid_projects.generation_mode vs document_runs.mode_used

`generation_mode` is the **project-level default**. `mode_used` is the **actual mode applied** for each run. They are expected to match, but `mode_used` may differ if:
- `strict_template` mode was requested but no matching template pack exists → fallback to `starter`
- This fallback is recorded in `document_runs.params_json` with a `mode_fallback_reason` field

`mode_used` is the authoritative record of what actually happened. `generation_mode` is the intent.

### checklist in doc_type Enum

`checklist` is a **generation artifact** produced during analysis, not by `document_runs`. Its lifecycle:
- Generated as part of `/api/analyze-rfp` response
- Stored in `document_revisions` with `content_schema = "checklist_v1"` and `source = "ai_generated"`
- Has NO `document_runs` row (run_id = NULL)
- Still tracked via `project_current_documents` for the "current checklist" pointer
- Can be manually edited (new revision with `source = "user_edited"`)

### Authorization Resolution: org role vs project access

```
Access check order:
1. memberships.role = "owner" or "admin" → FULL ACCESS to all projects in org
2. Otherwise → check project_access for (user_id, project_id)
   or (team_id, project_id) where user is team member
3. No matching project_access → DENIED (404)

Org admin does NOT need project_access rows.
Org editor/reviewer/viewer MUST have project_access to see a project.
```

### skill_versions.status = "shadow"

`shadow` means: the skill version is used to generate output in parallel with the `active` version, but only the `active` version's output is surfaced to the user. This enables A/B comparison before promotion. Shadow output is stored but not shown by default; reviewers can opt-in to compare.

### source_documents CHECK Constraints

- `document_kind = 'final_upload'` requires `project_id IS NOT NULL`
- `document_kind IN ('rfp', 'template', 'past_proposal', 'supporting_material')` allows `project_id IS NULL` (org-level shared documents)

---

## 12. Recommended Indexes

```sql
-- bid_projects
CREATE INDEX idx_bid_projects_org_status ON bid_projects(org_id, status);
CREATE INDEX idx_bid_projects_org_created ON bid_projects(org_id, created_at DESC);

-- analysis_snapshots: enforce single active per project
CREATE UNIQUE INDEX idx_analysis_active ON analysis_snapshots(project_id) WHERE is_active = true;

-- document_revisions
CREATE INDEX idx_doc_revisions_project_type ON document_revisions(project_id, doc_type, revision_number DESC);

-- document_assets
CREATE INDEX idx_doc_assets_org_project ON document_assets(org_id, project_id);
CREATE INDEX idx_doc_assets_revision ON document_assets(revision_id);

-- source_documents
CREATE INDEX idx_source_docs_project_kind ON source_documents(project_id, document_kind);

-- project_current_documents (already has UNIQUE(project_id, doc_type))
CREATE INDEX idx_current_docs_org ON project_current_documents(org_id);

-- memberships
CREATE INDEX idx_memberships_user ON memberships(user_id, org_id) WHERE is_active = true;
CREATE INDEX idx_memberships_org_role ON memberships(org_id, role) WHERE is_active = true;

-- project_access
CREATE INDEX idx_project_access_project ON project_access(project_id);
CREATE INDEX idx_project_access_user ON project_access(user_id);

-- review_requests
CREATE INDEX idx_reviews_project ON review_requests(project_id, status);

-- audit_logs (already specified in table definition)
CREATE INDEX idx_audit_org_time ON audit_logs(org_id, created_at DESC);
CREATE INDEX idx_audit_project_time ON audit_logs(project_id, created_at DESC);
CREATE INDEX idx_audit_target ON audit_logs(target_type, target_id);

-- company_track_records (pgvector)
CREATE INDEX idx_track_records_org ON company_track_records(org_id);

-- company_personnel (pgvector)
CREATE INDEX idx_personnel_org ON company_personnel(org_id);
```

---

## 13. Mutable Table Timestamps

Tables with `updated_at` (mutable state):
- `organizations`, `bid_projects`, `company_profiles` — already have `updated_at`
- `memberships` — add `updated_at` (role changes, deactivation)
- `project_access` — add `updated_at` (access level changes)

Tables WITHOUT `updated_at` (immutable by design):
- `analysis_snapshots` — immutable after creation
- `document_runs` — has `started_at`, `completed_at` instead
- `document_revisions` — immutable (new revision instead of edit-in-place)
- `document_assets` — immutable (soft delete via `is_deleted`)
- `approval_records` — immutable decision record
- `audit_logs` — append-only

---

## 14. Relationship Summary

| Concern | Source of Truth |
|---------|---------------|
| Tenant boundary | organizations |
| Business object | bid_projects |
| Analysis state | analysis_snapshots (immutable) |
| Generation execution | document_runs (async lifecycle) |
| Working document | document_revisions |
| Physical file location | document_assets.storage_uri (ONLY here) |
| Current active version | project_current_documents |
| Review/approval flow | review_requests + approval_records |
| Learning candidates | skill_update_candidates |
| Active skills | skill_versions |
| All actions | audit_logs (append-only) |

---

## 15. Prohibitions

- **Do NOT** keep session as the business lifecycle boundary.
- **Do NOT** store files on local filesystem for production assets.
- **Do NOT** create a separate users/auth table. Reuse existing Kira auth.
- **Do NOT** use company_id as a top-level tenant key. org_id only.
- **Do NOT** pass local file paths to rag_engine.
- **Do NOT** use SQLite. PostgreSQL from day one.
- **Do NOT** identify downloads by filename alone.
- **Do NOT** add new features to the session adapter.
- **Do NOT** store storage_uri in multiple tables. document_assets only.
- **Do NOT** mix blind check (document policy) into security gate (ACL/IDOR).
