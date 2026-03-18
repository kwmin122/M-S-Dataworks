# Bid Studio Master Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build Bid Studio as a package-first workspace that classifies required bid submission packages, stages company/style inputs safely, generates automatable documents, and tracks the remaining evidence/checklist items across services, goods, and construction.

**Architecture:** Keep Chat as an exploration surface and introduce Studio as the official production path. Reuse existing orchestrators for generation, add a package-classifier and project-scoped staging models, then cut over generation gradually behind feature flags.

**Tech Stack:** React + React Router + Tailwind, FastAPI, SQLAlchemy, PostgreSQL, Alembic, existing rag_engine orchestrators, pytest, TypeScript.

---

## Execution Order

Do not implement this plan horizontally.

Follow this sequence:

1. Front door and shell
2. Project + package control plane
3. First vertical slice: proposal
4. Second vertical slice: execution plan + checklist
5. Expansion: PPT + track record
6. Review/relearning
7. Cutover and hardening

---

### Task 1: Studio Front Door and Routing

**Files:**
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/App.tsx`
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/Hero.tsx`
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/Navbar.tsx`
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/landing/ProductHub.tsx`
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/services/authService.ts`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/StudioHome.tsx`
- Test: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/landing/__tests__/ProductHub.test.tsx`

**Step 1: Write the failing tests**

- Add a ProductHub render/navigation test:
  - logged out click on Studio card opens login path with `/studio` redirect target
  - logged in click navigates to `/studio`
- Add a small auth redirect test for `consumePostLoginTarget()` returning the stored path

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2/frontend/kirabot
npx vitest run components/landing/__tests__/ProductHub.test.tsx
```

Expected:

- fail because ProductHub is not inserted or redirect path behavior is incomplete

**Step 3: Write the minimal implementation**

- Insert `ProductHub` into landing below `Hero`
- Add `/studio` protected route placeholder
- Make auth post-login target path-based, not boolean
- Add logged-in navbar links for `/chat`, `/studio`, `/alerts`, `/forecast`

**Step 4: Run verification**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2/frontend/kirabot
npx vitest run components/landing/__tests__/ProductHub.test.tsx
npx tsc --noEmit
```

Expected:

- tests pass
- TypeScript clean

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add frontend/kirabot/App.tsx frontend/kirabot/components/Hero.tsx frontend/kirabot/components/Navbar.tsx frontend/kirabot/components/landing/ProductHub.tsx frontend/kirabot/components/studio/StudioHome.tsx frontend/kirabot/services/authService.ts frontend/kirabot/components/landing/__tests__/ProductHub.test.tsx
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): expose studio entry across landing and auth"
```

---

### Task 2: Studio Project Control Plane and DB Schema

**Files:**
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/db/models/project.py`
- Create: `.worktrees/bid-workspace-phase2/services/web_app/db/models/studio.py`
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/db/models/__init__.py`
- Create: `.worktrees/bid-workspace-phase2/services/web_app/db/migrations/versions/<timestamp>_add_studio_models.py`
- Create: `.worktrees/bid-workspace-phase2/services/web_app/api/studio.py`
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/main.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_studio_projects_api.py`

**Step 1: Write the failing tests**

Add tests for:

- `POST /api/studio/projects` creates a Studio project
- `from_analysis_snapshot_id` clones the source snapshot into the new project
- `GET /api/studio/projects` returns only org-owned projects

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_projects_api.py -q
```

Expected:

- fail because studio router/models/migration do not exist yet

**Step 3: Write the minimal implementation**

- Add Studio-specific columns to `BidProject`
- Create `ProjectCompanyAsset`, `ProjectStyleSkill`, `ProjectPackageItem`
- Create `/api/studio/projects` CRUD endpoints
- Include router in `main.py`
- Implement snapshot clone semantics

**Step 4: Run verification**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_projects_api.py -q
python -m py_compile services/web_app/api/studio.py services/web_app/db/models/project.py services/web_app/db/models/studio.py
```

Expected:

- tests pass
- py_compile clean

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add services/web_app/db/models/project.py services/web_app/db/models/studio.py services/web_app/db/models/__init__.py services/web_app/db/migrations/versions services/web_app/api/studio.py services/web_app/main.py services/web_app/tests/test_studio_projects_api.py
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): add studio project control plane and schema"
```

---

### Task 3: Studio Shell and Stage Navigation

**Files:**
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/StudioProject.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/StudioLayout.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/StageNav.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/ProjectContextPanel.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/services/studioApi.ts`
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/App.tsx`
- Test: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/__tests__/StageNav.test.tsx`

**Step 1: Write the failing tests**

- StageNav renders the seven stages
- current stage highlights correctly
- context panel shows project title and stage metadata

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2/frontend/kirabot
npx vitest run components/studio/__tests__/StageNav.test.tsx
```

Expected:

- fail because components do not exist

**Step 3: Write the minimal implementation**

- Add `/studio/projects/:id`
- Add left stage nav with:
  - 공고
  - 제출 패키지
  - 회사 역량
  - 스타일 학습
  - 생성
  - 검토/보완
  - 재학습
- Add right context panel with project summary

**Step 4: Run verification**

Run:

```bash
npx vitest run components/studio/__tests__/StageNav.test.tsx
npx tsc --noEmit
```

Expected:

- tests pass
- TypeScript clean

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add frontend/kirabot/components/studio frontend/kirabot/services/studioApi.ts frontend/kirabot/App.tsx
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): add studio shell and stage navigation"
```

---

### Task 4: RFP Intake and Package Classifier v1

**Files:**
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/RfpStage.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/PackageStage.tsx`
- Create: `.worktrees/bid-workspace-phase2/services/web_app/services/package_classifier.py`
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/api/studio.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_package_classifier.py`
- Test: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/__tests__/PackageStage.test.tsx`

**Step 1: Write the failing tests**

Backend tests:

- service negotiated RFP -> generated docs include proposal/presentation
- PQ-style project -> evidence items include PQ-related supporting materials
- goods spec-price project -> package includes spec/compliance artifacts

Frontend test:

- PackageStage renders generated/evidence/administrative groups

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
python -m pytest services/web_app/tests/test_package_classifier.py -q
cd frontend/kirabot && npx vitest run components/studio/__tests__/PackageStage.test.tsx
```

Expected:

- fail because classifier and stage UI do not exist

**Step 3: Write the minimal implementation**

- Add rule-based classifier v1 using `analysis_json` metadata + keyword heuristics
- Persist package items to `project_package_items`
- Add RFP analyze endpoints and PackageStage UI

**Step 4: Run verification**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
python -m pytest services/web_app/tests/test_package_classifier.py -q
cd frontend/kirabot && npx vitest run components/studio/__tests__/PackageStage.test.tsx && npx tsc --noEmit
```

Expected:

- tests pass

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add services/web_app/services/package_classifier.py services/web_app/api/studio.py frontend/kirabot/components/studio/stages/RfpStage.tsx frontend/kirabot/components/studio/stages/PackageStage.tsx services/web_app/tests/test_package_classifier.py frontend/kirabot/components/studio/__tests__/PackageStage.test.tsx
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): classify submission packages from analyzed rfp"
```

---

### Task 5: Company Staging and Promote Flow

**Files:**
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/CompanyStage.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/CompanyAssetList.tsx`
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/api/studio.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_studio_company_assets_api.py`

**Step 1: Write the failing tests**

- project company upload writes to staging table only
- promote writes selected assets to shared models and audit fields
- shared company data remains unchanged before promote

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_company_assets_api.py -q
```

Expected:

- fail because staging/promote endpoints do not exist

**Step 3: Write the minimal implementation**

- add upload/text/profile endpoints for staging
- add merged-view endpoint
- add promote endpoint with audit fields
- build CompanyStage UI against the merged view

**Step 4: Run verification**

Run:

```bash
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_company_assets_api.py -q
cd frontend/kirabot && npx tsc --noEmit
```

Expected:

- tests pass

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add services/web_app/api/studio.py services/web_app/tests/test_studio_company_assets_api.py frontend/kirabot/components/studio/stages/CompanyStage.tsx frontend/kirabot/components/studio/stages/CompanyAssetList.tsx
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): add project-scoped company staging and promote flow"
```

---

### Task 6: Style Skill Pin / Derive / Promote

**Files:**
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/StyleStage.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/StylePreview.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/StyleSkillManager.tsx`
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/api/studio.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_studio_style_skills_api.py`

**Step 1: Write the failing tests**

- analyzing uploaded past proposal creates a project-scoped style skill row
- pin updates `bid_projects.pinned_style_skill_id`
- promote marks a shared default and preserves derive lineage

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_style_skills_api.py -q
```

Expected:

- fail because style skill API does not exist

**Step 3: Write the minimal implementation**

- add analyze/save/pin/promote endpoints
- generate `profile_md_content` from extracted style profile
- add StyleStage and version manager UI

**Step 4: Run verification**

Run:

```bash
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_style_skills_api.py -q
cd frontend/kirabot && npx tsc --noEmit
```

Expected:

- tests pass

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add services/web_app/api/studio.py services/web_app/tests/test_studio_style_skills_api.py frontend/kirabot/components/studio/stages/StyleStage.tsx frontend/kirabot/components/studio/stages/StylePreview.tsx frontend/kirabot/components/studio/stages/StyleSkillManager.tsx
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): add style skill pinning and promotion"
```

---

### Task 7: First Vertical Slice - Proposal Generation

**Files:**
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/GenerateStage.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/GenerateContractView.tsx`
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/api/studio.py`
- Modify: `.worktrees/bid-workspace-phase2/rag_engine/proposal_orchestrator.py`
- Modify: `.worktrees/bid-workspace-phase2/rag_engine/section_writer.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_studio_generate_proposal_api.py`
- Test: `.worktrees/bid-workspace-phase2/rag_engine/tests/test_proposal_orchestrator.py`

**Step 1: Write the failing tests**

- Studio generate endpoint creates a run/revision for proposal
- generation contract includes snapshot id, project staging summary, pinned style id
- proposal generation changes when company/style inputs are present

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_generate_proposal_api.py -q
python -m pytest rag_engine/tests/test_proposal_orchestrator.py -q
```

Expected:

- fail because Studio generation path does not exist

**Step 3: Write the minimal implementation**

- add Studio generate endpoint for `doc_type=proposal`
- build effective company context from shared + staging
- load pinned style `profile_md_content`
- call existing proposal orchestrator
- persist generation contract metadata
- improve proposal prompt logging/quality assertions as needed

**Step 4: Run verification**

Run:

```bash
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_generate_proposal_api.py -q
python -m pytest rag_engine/tests/test_proposal_orchestrator.py -q
cd frontend/kirabot && npx tsc --noEmit
```

Expected:

- proposal Studio slice passes end-to-end

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add services/web_app/api/studio.py services/web_app/tests/test_studio_generate_proposal_api.py rag_engine/proposal_orchestrator.py rag_engine/section_writer.py frontend/kirabot/components/studio/stages/GenerateStage.tsx frontend/kirabot/components/studio/stages/GenerateContractView.tsx
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): add first vertical slice for proposal generation"
```

---

### Task 8: Second Vertical Slice - Execution Plan and WBS Quality

**Files:**
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/api/studio.py`
- Modify: `.worktrees/bid-workspace-phase2/rag_engine/wbs_orchestrator.py`
- Modify: `.worktrees/bid-workspace-phase2/rag_engine/wbs_planner.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_studio_generate_execution_plan_api.py`
- Test: `.worktrees/bid-workspace-phase2/rag_engine/tests/test_wbs_planner.py`

**Step 1: Write the failing tests**

- execution plan generation works through Studio
- research-style RFP does not regress to IT-only stage language
- date-range duration parsing handles common forms

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_generate_execution_plan_api.py -q
python -m pytest rag_engine/tests/test_wbs_planner.py -q
```

Expected:

- fail because Studio execution path and quality assertions are incomplete

**Step 3: Write the minimal implementation**

- add Studio execution-plan generate path
- fix WBS duration parsing with shared parser helper if needed
- relax IT-specific prompt constraints and roles
- align execution plan output with package item state

**Step 4: Run verification**

Run:

```bash
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_generate_execution_plan_api.py -q
python -m pytest rag_engine/tests/test_wbs_planner.py -q
```

Expected:

- tests pass with domain-appropriate execution-plan behavior

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add services/web_app/api/studio.py services/web_app/tests/test_studio_generate_execution_plan_api.py rag_engine/wbs_orchestrator.py rag_engine/wbs_planner.py rag_engine/tests/test_wbs_planner.py
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): add execution plan generation and improve wbs quality"
```

---

### Task 9: Package Checklist and Evidence Management

**Files:**
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/ChecklistStage.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/EvidenceUploadPanel.tsx`
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/api/studio.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_studio_package_items_api.py`

**Step 1: Write the failing tests**

- package items transition from `missing` to `generated` or `uploaded`
- evidence uploads can attach to package items
- checklist completeness summary is computed correctly

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_package_items_api.py -q
```

Expected:

- fail because package item lifecycle endpoints are incomplete

**Step 3: Write the minimal implementation**

- add package item update/upload endpoints
- connect generated runs to package item satisfaction
- add checklist UI and evidence upload panel

**Step 4: Run verification**

Run:

```bash
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_package_items_api.py -q
cd frontend/kirabot && npx tsc --noEmit
```

Expected:

- tests pass

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add services/web_app/api/studio.py services/web_app/tests/test_studio_package_items_api.py frontend/kirabot/components/studio/stages/ChecklistStage.tsx frontend/kirabot/components/studio/stages/EvidenceUploadPanel.tsx
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): add checklist and evidence management"
```

---

### Task 10: PPT and Track Record Expansion

**Files:**
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/api/studio.py`
- Modify: `.worktrees/bid-workspace-phase2/rag_engine/ppt_orchestrator.py`
- Modify: `.worktrees/bid-workspace-phase2/rag_engine/ppt_slide_planner.py`
- Modify: `.worktrees/bid-workspace-phase2/rag_engine/track_record_orchestrator.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_studio_generate_ppt_api.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_studio_generate_track_record_api.py`

**Step 1: Write the failing tests**

- Studio generates PPT and track record outputs
- package items update correctly
- domain-specific context affects output content

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_generate_ppt_api.py services/web_app/tests/test_studio_generate_track_record_api.py -q
```

Expected:

- fail because Studio routes for these doc types do not exist

**Step 3: Write the minimal implementation**

- extend generate endpoint for `ppt` and `track_record`
- connect outputs to package items
- add any necessary prompt quality adjustments

**Step 4: Run verification**

Run:

```bash
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_generate_ppt_api.py services/web_app/tests/test_studio_generate_track_record_api.py -q
python -m pytest rag_engine/tests/test_ppt_orchestrator.py rag_engine/tests/test_track_record_orchestrator.py -q
```

Expected:

- tests pass

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add services/web_app/api/studio.py services/web_app/tests/test_studio_generate_ppt_api.py services/web_app/tests/test_studio_generate_track_record_api.py rag_engine/ppt_orchestrator.py rag_engine/ppt_slide_planner.py rag_engine/track_record_orchestrator.py
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): expand generation to ppt and track record"
```

---

### Task 11: Review, Feedback, and Relearning

**Files:**
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/ReviewStage.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/DiffView.tsx`
- Create: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/studio/stages/RelearnDialog.tsx`
- Modify: `.worktrees/bid-workspace-phase2/services/web_app/api/studio.py`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_studio_relearn_api.py`

**Step 1: Write the failing tests**

- uploading edited document creates feedback record
- relearn derives a new project-scoped style version
- pinned style can be switched to the new version without modifying shared default

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_relearn_api.py -q
```

Expected:

- fail because feedback/relearn flow does not exist

**Step 3: Write the minimal implementation**

- add feedback upload endpoint
- add relearn endpoint deriving a new style skill version
- expose review UI and diff panel

**Step 4: Run verification**

Run:

```bash
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests/test_studio_relearn_api.py -q
cd frontend/kirabot && npx tsc --noEmit
```

Expected:

- tests pass

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add services/web_app/api/studio.py services/web_app/tests/test_studio_relearn_api.py frontend/kirabot/components/studio/stages/ReviewStage.tsx frontend/kirabot/components/studio/stages/DiffView.tsx frontend/kirabot/components/studio/stages/RelearnDialog.tsx
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): add review and relearning workflow"
```

---

### Task 12: Cutover, Hardening, and Real-World Verification

**Files:**
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/chat/messages/AnalysisResultView.tsx`
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/hooks/useConversationFlow.ts`
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/Navbar.tsx`
- Modify: `.worktrees/bid-workspace-phase2/frontend/kirabot/components/settings/SettingsCompany.tsx`
- Test: `.worktrees/bid-workspace-phase2/services/web_app/tests/test_chat_to_studio_cutover.py`

**Step 1: Write the failing tests**

- chat generation CTA respects `chat_generation_cutover`
- chat handoff to Studio creates a project and lands on the correct route
- company DB surfaces in Chat are reduced to status + CTA

**Step 2: Run the tests to confirm failure**

Run:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
python -m pytest services/web_app/tests/test_chat_to_studio_cutover.py -q
```

Expected:

- fail because cutover behavior is not implemented

**Step 3: Write the minimal implementation**

- enable `studio_visible`
- add `chat_generation_cutover`
- switch chat generation buttons to Studio CTA after verification
- reduce Chat company DB editing surface

**Step 4: Run verification**

Run:

```bash
python -m pytest services/web_app/tests/test_chat_to_studio_cutover.py -q
cd frontend/kirabot && npx tsc --noEmit
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2/rag_engine && python -m pytest -q
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 && BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests -q
```

Expected:

- cutover passes
- frontend typecheck passes
- backend suites remain green

**Step 5: Commit**

```bash
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 add frontend/kirabot/components/chat/messages/AnalysisResultView.tsx frontend/kirabot/hooks/useConversationFlow.ts frontend/kirabot/components/Navbar.tsx frontend/kirabot/components/settings/SettingsCompany.tsx services/web_app/tests/test_chat_to_studio_cutover.py
git -C /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2 commit -m "feat(studio): cut over generation entrypoints to studio"
```

---

## Final Verification

Run this after all tasks:

```bash
cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2/frontend/kirabot
npx tsc --noEmit

cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2/rag_engine
python -m pytest -q

cd /Users/min-kyungwook/Desktop/MS_SOLUTIONS/.worktrees/bid-workspace-phase2
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' python -m pytest services/web_app/tests -q
python -m pytest tests -q
```

Then perform manual full-cycle checks for:

1. service negotiated RFP
2. PQ-style technical project
3. goods or construction package example

Verify:

- package classification accuracy
- generated docs are linked to package items
- evidence gaps are visible
- relearn produces a new style version
- Chat cutover sends users to Studio

---

## Notes

- Do not try to perfect all domains before Slice 1 is end-to-end.
- Do not remove Chat generation until Studio is proven with real RFPs.
- Treat package-classifier mistakes as product blockers, not cosmetic issues.
- Prefer shared helpers for effective company context and generation contract assembly rather than duplicating logic in each endpoint.
