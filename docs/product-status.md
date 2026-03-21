# Kira Bot — Product Status (Single Source of Truth)

> **이 문서는 운영 truth 문서입니다. 영업 문서(kirabot_features.md)와 구분하세요.**
> **Historical handoff: docs/handoff-2026-03-21.md**

> Last updated: 2026-03-21
> This document reflects ACTUAL production and code state. Not aspirational.
> Cross-referenced against running code, git history, and Dockerfile.

---

## Production Status

### Deployed & Active (Railway Production)

These features are committed to `main`, built into the Docker image, and serving traffic.

| Feature | Evidence |
|---------|----------|
| **Landing page** (Hero, ProductHub, HowItWorks, Solutions, Pricing, Footer) | `frontend/kirabot/App.tsx:182-220` |
| **Google OAuth + Kakao login** | `services/web_app/main.py:1384-1519` |
| **Chat Hub** — 대화형 공고 탐색, RFP 분석, GO/NO-GO, Q&A | `services/web_app/main.py:2124-2699` |
| **나라장터 공고 검색** (Chat) | `services/web_app/main.py:2254` — `POST /api/bids/search` |
| **RFP 문서 분석** — PDF/DOCX/HWP/HWPX/TXT multipass extraction | `services/web_app/main.py:1834-2092` |
| **GO/NO-GO 판단** — ConstraintEvaluator + LLM fallback | `matcher.py`, `rfx_analyzer.py` |
| **일괄 공고 평가** (최대 50건) | `services/web_app/main.py:2552` — `POST /api/bids/evaluate-batch` |
| **제안서 생성 (Legacy v1)** | `services/web_app/main.py:2700` — `POST /api/proposal/generate` |
| **제안서 생성 v2 (A-lite)** | `services/web_app/main.py:2845` — `POST /api/proposal/generate-v2` |
| **WBS 생성** | `services/web_app/main.py:2948` — proxy to rag_engine |
| **PPT 생성** (KRDS 디자인) | `services/web_app/main.py:2982` — proxy to rag_engine |
| **실적기술서 생성** | `services/web_app/main.py:3003` — proxy to rag_engine |
| **제안서 섹션 편집 + DOCX 재조립** | `services/web_app/main.py:3158-3177` — proxy to rag_engine |
| **CompanyDB** — 프로필/실적/인력 CRUD, 멀티테넌시 | `services/web_app/main.py:3044-3147`, rag_engine endpoints |
| **Company Document Pack** — 업로드, 파싱, AI 프로필 자동 추출 | `services/web_app/main.py:1706-1832` |
| **DocumentWorkspace** — WYSIWYG 프로필 편집 + 버전 히스토리 | `frontend/kirabot/components/settings/documents/DocumentWorkspace.tsx` |
| **알림 시스템** — 키워드 매칭, 이메일(Brevo), 스케줄러(30분 루프) | `services/web_app/main.py:3194-3746`, `_alert_scheduler_loop` at line 4834 |
| **대시보드** — 사용 현황, 월별 추적 | `services/web_app/main.py:3752` |
| **Smart Fit Score** | `services/web_app/main.py:3813` — `POST /api/smart-fit/score` |
| **발주 예측** — 인기기관 TOP 10 + 기관별 추세 | `services/web_app/main.py:3883-3897` |
| **Bid Studio (Slice 1-5)** — 7단계 워크플로우 | `services/web_app/api/studio.py` — 32 endpoints, conditionally loaded when `BID_DATABASE_URL` is set (`main.py:252-260`) |
| **Studio ACL** — 5단계 접근 제어 (viewer~owner) | `services/web_app/api/deps.py` — `require_project_access` |
| **Package Classifier** — 키워드 스코어링 + 수의계약 하드가드 + 18건 코퍼스 | `services/web_app/services/package_classifier.py` |
| **Rate Limiting** — SlowAPIMiddleware (전역 60/분) + 엔드포인트별 | `services/web_app/main.py:247-249`, `services/web_app/rate_limit.py` |
| **Ops Hardening** — upload allowlist, path traversal guard, CORS pinning | Committed in `4722d99`, `edcf260`, `427e33e` |
| **결제 (PortOne)** — 빌링키 등록, 구독 조회/취소, 웹훅 | `services/web_app/main.py:4960-5098` |
| **Layer 1** — 495 유닛 ChromaDB (블로그47+유튜브40+문서18) | `rag_engine/`, ChromaDB warmup in `start.sh:86-91` |
| **Layer 2** — auto_learner 영속성 (lifespan load/save) | `rag_engine/main.py` lifespan |
| **RAG Engine** — 별도 프로세스 port 8001, web_app이 proxy | `start.sh:40-83`, `Dockerfile:48` |

### Committed, Not Yet Deployed

These features are committed to `main` but not yet deployed to Railway production.

| Feature | Commit | Notes |
|---------|--------|-------|
| **나라장터 검색 (Studio RFP Stage)** | `98dac35` | Search panel with keyword + category + pagination |
| **RFP 파일 업로드 (Studio)** | `98dac35` | Upload PDF/DOCX via Studio UI, parse + analyze |
| **계정 삭제** | `98dac35`, `36c3736` | Email confirmation modal + deactivation guard |
| **보안 핫픽스 P0 (4건)** | `98dac35` | 8KB streaming size check, try/finally cleanup, path traversal, magic bytes |
| **Rate Limit: search-bids** | `98dac35` | `@limiter.limit("10/minute")` on search endpoint |
| **입력 검증: NaraSearchRequest** | `98dac35` | `Literal` category, `ge/le` page bounds |
| **Studio 레이아웃 수정** | `98dac35` | Chat sidebar hidden in /studio/*, top nav bar added |
| **제안서 V2 프롬프트** | `98dac35` | 3,017-char structured prompt, max_tokens 8000, temp 0.35, env-based model |
| **품질 검사기 25개 금지패턴** | `98dac35` | Expanded from 7 to 25 patterns + domain-dynamic load |
| **rate_limit.py 모듈화** | `98dac35` | Shared Limiter instance extracted |
| **계정 삭제 후 재로그인 가드** | `36c3736` | `is_active=False` 체크 추가 (deps.py) |
| **Quality Gate UI** | `36c3736` | 품질 점수 사용자 표시 |
| **파일 타입 검증 강화** | `b956272` | File type validation + endpoint tests |
| **WBS Quality (Phase 3A-1)** | `c19cd9d` | Domain-aware WBS + quality gate + font fix |
| **Presentation Quality (Phase 3A-2)** | `f1e72e5` | Presentation evidence gate + domain slides + quality checks |

#### Untracked Files (NOT committed, NOT deployed)

| Feature | Files | Notes |
|---------|-------|-------|
| **A/B 테스트 스크립트** | `scripts/ab_test_proposal_quality.py` | V1 vs V2 comparison automation |
| **A/B 테스트 결과** | `docs/ab_test_result.md` | V1: 69/80, V2: 75/80 (+6점) |
| **PDF 브로셔** | `docs/kirabot_brochure.pdf`, `scripts/generate_brochure_pdf.py` | 12-page marketing PDF |
| **기능 목록 문서** | `docs/kirabot_features.md` | Marketing/sales document (aspirational in parts) |
| **핸드오프 문서** | `docs/handoff-2026-03-21.md` | Session handoff notes |

### Feature-Gated (Code Exists, Flag Controls Behavior)

| Flag | Code Default | Dockerfile Default | Production Value | Effect When ON | Effect When OFF |
|------|-------------|-------------------|-----------------|----------------|-----------------|
| `VITE_STUDIO_VISIBLE` | `true` (studioApi.ts:71) | `true` (Dockerfile:4) | `true` | Studio link in Navbar, Hero CTA, ProductHub card visible | Studio links hidden (route still accessible via direct URL) |
| `VITE_CHAT_GENERATION_CUTOVER` | `false` (studioApi.ts:75) | `false` (Dockerfile:5) | `false` | Chat analysis result shows "Studio에서 입찰 문서 작성" CTA instead of legacy inline generate buttons | Legacy inline generate buttons in Chat (current behavior) |
| `BID_DATABASE_URL` | N/A | N/A | Set (Railway PG) | Studio routers loaded (`main.py:252-260`), DB tables created | Studio API entirely absent — 404 on all `/api/studio/*` |

**Current production state**: Studio is visible and accessible (`VITE_STUDIO_VISIBLE=true`), but Chat-to-Studio handoff is OFF (`VITE_CHAT_GENERATION_CUTOVER=false`). Users can access Studio directly but Chat still uses legacy inline generation buttons.

### Planned / Not Started (No Code Exists)

| Feature | Mentioned In | Status |
|---------|-------------|--------|
| **Layer 3 — 승패 분석** | `MEMORY.md`, `kirabot_features.md` | No code. Only mentioned as "예정" in docs. |
| **생성 후 검증 에이전트 (2-pass)** | `handoff-2026-03-21.md` 품질 로드맵 #1 | Idea only. No code. |
| **RFP 평가기준-섹션 정렬 스코어링** | `handoff-2026-03-21.md` 품질 로드맵 #2 | Idea only. No code. |
| **실적기술서 의미 기반 선택** | `handoff-2026-03-21.md` 품질 로드맵 #3 | Idea only. `select_track_records()` is sequential, not RFP-matched. |
| **Layer 1 도메인 태깅** | `handoff-2026-03-21.md` P2-5 | No tagging exists. 495 units are untagged in ChromaDB. |
| **에이전틱 AI 아키텍처** | `handoff-2026-03-21.md` 아이디어 | Concept only. No code. |
| **온프레미스 배포** | `kirabot_features.md` Pricing table | No code or infrastructure. Marketing claim only. |
| **전담 학습 모델 (Enterprise)** | `kirabot_features.md` Pricing table | No code. Marketing claim only. |

### Known Limitations (Honest Assessment)

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| 1 | **계정 삭제 후 재로그인 시 org 재생성** | ~~P1~~ **Fixed** | Commit `36c3736` — `is_active=False` deactivation guard 추가됨 |
| 2 | **upload-rfp에 rate limit 없음** | P1 | `studio.py:453` — LLM 호출 포함 고비용 엔드포인트에 rate limit 미적용. (Committed, not deployed) |
| 3 | ~~**신규 3개 엔드포인트 테스트 없음**~~ | ~~P1~~ **Fixed** | Commit `b956272` — endpoint tests 추가됨 |
| 4 | **HWP/TXT magic bytes 미검증** | P1 | `studio.py:503-514` — PDF/DOCX/XLSX/PPTX만 magic bytes 검증. HWP/TXT는 구조상 magic bytes 없음. |
| 5 | **Vite chunk 크기 경고** | P2 | `index.js` 1235KB, `MarkdownEditor` 568KB — code-splitting 미적용 |
| 6 | **검색 경쟁 조건** | P2 | RfpStage 검색 중 키워드 변경 시 이전 결과 덮어쓰기. AbortController 필요. |
| 7 | **미인증 /studio redirect 미작동** | P2 | `ProtectedRoute`가 `redirect` param 추가하지만 소비 코드 없음 |
| 8 | **Studio stage URL 미반영** | P2 | 브라우저 뒤로가기가 stage 단위로 안 됨 |
| 9 | **실적기술서 선택이 순차적** | P2 | `select_track_records()` — RFP 매칭 없이 순서대로 선택. 점수 5.5/10 수준. |
| 10 | **web_saas 미배포** | Info | `web_saas/` (Next.js + Prisma) 디렉토리 존재하나 Dockerfile에 포함 안 됨. 현재 미사용. |
| 11 | **pytest deprecation 경고 32건** | P3 | asyncio_default_fixture_loop_scope, chromadb, starlette cookies |
| 12 | **요금제 구분 미시행** | Info | 코드에 FREE/PRO 구분 로직 있으나 (`enforce_usage_quota`), 실질적으로 모든 사용자가 동일 기능 접근 가능. PortOne 결제 연동은 존재하나 과금 게이트 미완성. |

---

## API Endpoint Status

### web_app (port 8000) — Main Server

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/api/health` | GET | **LIVE** | Health check |
| `/auth/google/login` | GET | **LIVE** | Google OAuth redirect |
| `/auth/google/callback` | GET | **LIVE** | Google OAuth callback |
| `/auth/kakao/login` | GET | **LIVE** | Kakao OAuth redirect |
| `/auth/kakao/callback` | GET | **LIVE** | Kakao OAuth callback |
| `/auth/me` | GET | **LIVE** | Current user info |
| `/auth/logout` | POST | **LIVE** | Session logout |
| `/api/session` | POST | **LIVE** | Legacy session create |
| `/api/session/check` | POST | **LIVE** | Legacy session check |
| `/api/session/stats` | POST | **LIVE** | Usage stats |
| `/api/bids/search` | POST | **LIVE** | 나라장터 검색 (Chat) |
| `/api/bids/{id}/attachments` | GET | **LIVE** | 첨부파일 목록 |
| `/api/bids/analyze` | POST | **LIVE** | 공고 직접 분석 |
| `/api/bids/evaluate-batch` | POST | **LIVE** | 일괄 평가 |
| `/api/analyze/upload` | POST | **LIVE** | RFP 파일 분석 |
| `/api/analyze/text` | POST | **LIVE** | RFP 텍스트 분석 |
| `/api/chat` | POST | **LIVE** | 문서 기반 채팅 |
| `/api/chat/general` | POST | **LIVE** | 일반 채팅 |
| `/api/rematch` | POST | **LIVE** | 회사 문서 재매칭 |
| `/api/proposal/generate` | POST | **LIVE** | 제안서 생성 (Legacy v1) |
| `/api/proposal/generate-v2` | POST | **LIVE** | 제안서 v2 (A-lite) |
| `/api/proposal/download/{fn}` | GET | **LIVE** | DOCX 다운로드 |
| `/api/proposal/checklist` | POST | **LIVE** | 체크리스트 |
| `/api/proposal/generate-wbs` | POST | **LIVE** | WBS 생성 proxy |
| `/api/proposal/generate-ppt` | POST | **LIVE** | PPT 생성 proxy |
| `/api/proposal/generate-track-record` | POST | **LIVE** | 실적기술서 proxy |
| `/api/proposal-sections` | GET | **LIVE** | 섹션 조회 proxy |
| `/api/proposal-sections` | PUT | **LIVE** | 섹션 수정 proxy |
| `/api/proposal-sections/reassemble` | POST | **LIVE** | DOCX 재조립 proxy |
| `/api/company-db/*` (10 endpoints) | Various | **LIVE** | CompanyDB CRUD |
| `/api/company/*` (7 endpoints) | Various | **LIVE** | 회사 문서 관리 |
| `/api/profile-md/*` (4 endpoints) | Various | **LIVE** | 프로필 마크다운 proxy |
| `/api/alerts/*` (8 endpoints) | Various | **LIVE** | 알림 설정/발송 |
| `/api/dashboard/summary` | GET | **LIVE** | 사용 현황 |
| `/api/smart-fit/score` | POST | **LIVE** | Smart Fit Score |
| `/api/forecast/*` (2 endpoints) | Various | **LIVE** | 발주 예측 |
| `/api/payments/*` (5 endpoints) | Various | **LIVE** | PortOne 결제 |

### web_app — Studio Endpoints (conditional on `BID_DATABASE_URL`)

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/api/studio/projects` | POST | **LIVE** | `studio.py:161` |
| `/api/studio/projects` | GET | **LIVE** | `studio.py:225` |
| `/api/studio/projects/{id}` | GET | **LIVE** | `studio.py:260` |
| `/api/studio/projects/{id}/stage` | PATCH | **LIVE** | `studio.py:280` |
| `/api/studio/handoff-from-chat` | POST | **LIVE** | `studio.py:101` |
| `/api/studio/projects/{id}/analyze` | POST | **LIVE** | `studio.py:340` |
| `/api/studio/projects/{id}/classify` | POST | **LIVE** | `studio.py:622` |
| `/api/studio/projects/{id}/package-override` | PATCH | **LIVE** | `studio.py:756` |
| `/api/studio/projects/{id}/package-items` | GET | **LIVE** | `studio.py:894` |
| `/api/studio/projects/{id}/package-items/{item}/status` | PATCH | **LIVE** | `studio.py:2294` |
| `/api/studio/projects/{id}/package-items/{item}/evidence` | POST | **LIVE** | `studio.py:2327` |
| `/api/studio/projects/{id}/package-completeness` | GET | **LIVE** | `studio.py:2437` |
| `/api/studio/projects/{id}/package-items/{item}/evidence/download` | GET | **LIVE** | `studio.py:2507` |
| `/api/studio/projects/{id}/company-assets` | POST | **LIVE** | `studio.py:972` |
| `/api/studio/projects/{id}/company-assets` | GET | **LIVE** | `studio.py:996` |
| `/api/studio/projects/{id}/company-assets/{asset}/promote` | POST | **LIVE** | `studio.py:1121` |
| `/api/studio/projects/{id}/company-merged` | GET | **LIVE** | `studio.py:1014` |
| `/api/studio/projects/{id}/style-skills` | POST | **LIVE** | `studio.py:1313` |
| `/api/studio/projects/{id}/style-skills` | GET | **LIVE** | `studio.py:1359` |
| `/api/studio/projects/{id}/style-skills/{skill}/pin` | POST | **LIVE** | `studio.py:1380` |
| `/api/studio/projects/{id}/style-skills/pin` | DELETE | **LIVE** | `studio.py:1421` |
| `/api/studio/projects/{id}/style-skills/{skill}/derive` | POST | **LIVE** | `studio.py:1450` |
| `/api/studio/projects/{id}/style-skills/{skill}/promote` | POST | **LIVE** | `studio.py:1497` |
| `/api/studio/projects/{id}/generate` | POST | **LIVE** | `studio.py:1609` |
| `/api/studio/projects/{id}/documents/{type}/current` | GET | **LIVE** | `studio.py:1947` |
| `/api/studio/projects/{id}/documents/proposal/edited` | POST | **LIVE** | `studio.py:2011` |
| `/api/studio/projects/{id}/documents/proposal/diff` | GET | **LIVE** | `studio.py:2075` |
| `/api/studio/projects/{id}/documents/presentation/download` | GET | **LIVE** | `studio.py:2467` |
| `/api/studio/projects/{id}/relearn` | POST | **LIVE** | `studio.py:2116` |
| `/api/studio/search-bids` | POST | **COMMITTED** | `studio.py:318` — commit `98dac35`, not yet deployed |
| `/api/studio/projects/{id}/upload-rfp` | POST | **COMMITTED** | `studio.py:453` — commit `98dac35`, not yet deployed |
| `/api/studio/account` | DELETE | **COMMITTED** | `studio.py:2810` — commit `98dac35`, not yet deployed |

### rag_engine (port 8001) — AI Generation Engine

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/health`, `/healthz` | GET | **LIVE** | Health checks |
| `/warmup` | GET | **LIVE** | ChromaDB init |
| `/api/analyze-bid` | POST | **LIVE** | RFP 분석 |
| `/api/generate-proposal` | POST | **LIVE** | 제안서 v1 |
| `/api/generate-proposal-v2` | POST | **LIVE** | 제안서 v2 (A-lite) |
| `/api/generate-wbs` | POST | **LIVE** | WBS 생성 |
| `/api/generate-ppt` | POST | **LIVE** | PPT 생성 |
| `/api/generate-track-record` | POST | **LIVE** | 실적기술서 |
| `/api/checklist` | POST | **LIVE** | 체크리스트 |
| `/api/edit-feedback` | POST | **LIVE** | 편집 피드백 |
| `/api/company-db/*` (11 endpoints) | Various | **LIVE** | CompanyDB direct access |
| `/api/company-profile/*` (8 endpoints) | Various | **LIVE** | 회사 프로필 관리 |
| `/api/parse-hwp` | POST | **LIVE** | HWP 파싱 |
| `/api/proposal-sections/*` (3 endpoints) | Various | **LIVE** | 섹션 편집/재조립 |
| `/api/pending-knowledge` | GET | **LIVE** | 미승인 지식 조회 |
| `/api/approve-knowledge` | POST | **LIVE** | 지식 승인 |
| `/api/reject-knowledge` | DELETE | **LIVE** | 지식 거부 |

---

## UI Route Status

| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/` | Landing page (Hero+ProductHub+HowItWorks+Solutions+Pricing) | **LIVE** | `App.tsx:226` |
| `/privacy` | PrivacyPolicy | **LIVE** | `App.tsx:229` |
| `/terms` | TermsOfService | **LIVE** | `App.tsx:236` |
| `/chat` | ChatPage | **LIVE** (protected) | `App.tsx:254` |
| `/studio` | StudioHome | **LIVE** (protected) | `App.tsx:255` — requires `BID_DATABASE_URL` for backend |
| `/studio/projects/:projectId` | StudioProjectPage | **LIVE** (protected) | `App.tsx:256` — 7-stage workflow |
| `/alerts` | AlertsPage | **LIVE** (protected) | `App.tsx:257` |
| `/forecast` | ForecastPage | **LIVE** (protected) | `App.tsx:258` |
| `/admin` | AdminPage | **LIVE** (admin-only) | `App.tsx:259` |
| `/settings` | SettingsPage (nested) | **LIVE** (protected) | `App.tsx:262` |
| `/settings/general` | SettingsGeneral | **LIVE** | `App.tsx:263` |
| `/settings/company` | SettingsCompany | **LIVE** | `App.tsx:265` — CompanyDB 온보딩 |
| `/settings/usage` | DashboardPage | **LIVE** | `App.tsx:266` |
| `/settings/subscription` | SubscriptionPage | **LIVE** | `App.tsx:267` |
| `/settings/account` | SettingsAccount | **COMMITTED** (not deployed) | `App.tsx:268` — 삭제 기능 포함, commit `98dac35`+`36c3736` |
| `/settings/documents` | DocumentWorkspace | **LIVE** | `App.tsx:269` — WYSIWYG 편집 |
| `/dashboard` | Redirect to `/settings/usage` | **LIVE** | `App.tsx:273` — legacy redirect |

---

## Feature Flag Status

| Flag | Code Default | Dockerfile Default | Production Value | Effect |
|------|-------------|-------------------|-----------------|--------|
| `VITE_STUDIO_VISIBLE` | `true` (`studioApi.ts:71` — `!== 'false'`) | `true` (`Dockerfile:4`) | `true` | Controls: Navbar "입찰 문서 AI 작성" link (`Navbar.tsx:40`), Hero Studio CTA (`App.tsx:192`), ProductHub Studio card (`App.tsx:198`). Route `/studio` is always accessible regardless. |
| `VITE_CHAT_GENERATION_CUTOVER` | `false` (`studioApi.ts:75` — `=== 'true'`) | `false` (`Dockerfile:5`) | `false` | Controls: AnalysisResultView shows Studio handoff CTA vs legacy inline generate buttons (`AnalysisResultView.tsx:255`). Currently OFF = users see legacy generate buttons in Chat. |
| `BID_DATABASE_URL` | N/A (env-only) | Not set in Dockerfile | Set (Railway PostgreSQL) | Controls: Studio router registration (`main.py:252-260`). Without it, all `/api/studio/*` returns 404. |
| `BID_DEV_BOOTSTRAP` | N/A | Not set | **Must NOT be set in production** | Auto-provisions orgs for any user. Production uses manual DB INSERT per `2026-03-20-production-deploy-checklist.md:40`. |

---

## Quality Metrics

### Test Counts (as of last verified run)

| Suite | Count | Command | Notes |
|-------|-------|---------|-------|
| rag_engine pytest | 397 passed | `cd rag_engine && pytest -q` | Verified in handoff-2026-03-21 |
| Frontend vitest | 109 passed | `cd frontend/kirabot && npx vitest run` | Verified in handoff-2026-03-21 |
| Studio BE pytest | 45+ (estimated) | `python -m pytest services/web_app/tests -q` | Requires PostgreSQL; count from commit `a81e71c` |
| Root pytest | ~202 | `pytest -q` | Legacy tests |
| Package classifier regression | 18 cases | Parametrized in `services/web_app/tests/` | Commit `b593498` |

### A/B Test Results (Proposal Quality)

Source: `docs/ab_test_result.md` (untracked file)

| Metric | V1 (기존 4줄 프롬프트) | V2 (구조화 프롬프트) |
|--------|---------------------|-------------------|
| 총점 | 69/80 | 75/80 |
| 등급 | 우 (64+) | **수 (72+)** |
| 근거/수치 밀도 | 7/10 | **10/10** (+3) |
| 모델 | gpt-4o-mini | gpt-4o-mini |
| 섹션 | 사업이해도 (배점 20) | 사업이해도 (배점 20) |

NOTE: The V2 prompt changes (`section_writer.py` + `rag_engine/prompts/`) are committed (commit `98dac35`) but not yet deployed. The A/B test script and results doc remain untracked.

---

## Distinction: 영업 문서 vs 운영 문서

`docs/kirabot_features.md` is a **marketing/sales document**. Several claims in it do not match production reality:

| kirabot_features.md Claim | Reality |
|---------------------------|---------|
| "Layer 3: 승패 분석" (Section 2) | **No code exists.** Listed as "예정" even in the doc itself. |
| "500+ 자동화 테스트" (Section 11.3) | Actual total: ~397 (rag) + 109 (FE) + ~45 (Studio) + ~202 (root) = ~753 total, but includes overlaps. The "500+" figure is approximately correct but imprecise. |
| "88+ API 엔드포인트" (Section 14) | Plausible when counting all routers, but some are debug-only, some are proxies to rag_engine. Real unique user-facing endpoints are fewer. |
| "온프레미스 배포" (Enterprise tier) | No infrastructure or docs for on-premise deployment. |
| "전담 학습 모델" (Enterprise tier) | No code for dedicated model training. |
| "SLA + 전담 지원" (Enterprise tier) | No SLA documentation or support tooling. |
| "카카오 로그인" (Section 9.2) | Code exists and is deployed (`main.py:1453`). |
| "알림 미리보기" (Section 7.3) | Code exists: `POST /api/alerts/preview` (`main.py:3666`). |
| "다중 포맷 지원: HWP, HWPX" (Section 3.2) | Code exists for HWP (`hwp_parser.py`) and HWPX (`document_parser.py`). HWPX was added in commit `b6a337d`. However, HWP parsing quality varies — it uses `olefile` extraction which can miss complex layouts. |

**This document (`product-status.md`) is the operational source of truth. `kirabot_features.md` is for external communication.**

---

## Architecture Summary (Actual Deployment)

```
Railway Production (single service):
  start.sh
    ├── rag_engine (uvicorn, port 8001) — AI generation, ChromaDB, CompanyDB
    │     └── ChromaDB warmup on startup
    └── web_app (uvicorn, port $PORT=8000) — Main API + static frontend
          ├── SPA frontend (React 19 + Vite, built in Docker Stage 1)
          ├── Chat APIs (direct)
          ├── Studio APIs (conditional on BID_DATABASE_URL)
          │     └── PostgreSQL (Railway addon)
          ├── Legacy APIs (proxy to rag_engine)
          ├── Alert scheduler (asyncio background task, 30min loop)
          └── PortOne payment webhooks

NOT deployed:
  web_saas/ — Next.js + Prisma stack exists in repo but is NOT in Dockerfile.
              Not built, not served, not connected to production.
```

---

## 이번 배치 완료 범위 (2026-03-21)

### 완료 (12/17)
| # | 요구사항 | 구현 내용 | 검증 상태 |
|---|---------|----------|----------|
| 1 | Single Source of Truth | product-status.md 생성 | ✅ Committed |
| 2 | No Dead Ends | 나라장터 검색 + 파일 업로드 + 계정 삭제 | ✅ Committed (`98dac35`, `36c3736`) |
| 3 | Manual Override | 도메인/계약방식/PPT/항목 CRUD + AuditLog | ✅ Committed (`98dac35`) |
| 4 | Package Completeness | 면제/삭제/추가 + 진행률 | ✅ Committed (`98dac35`) |
| 5 | Generation Quality Gate | 7차원 품질 스코어링 (quality_gate.py) | ✅ Committed (`98dac35`) + UI (`36c3736`) |
| 6 | Proposal Quality | V2 프롬프트 + A/B 69→75점 | ✅ Committed (`98dac35`) |
| 7 | WBS Quality | Domain-aware WBS + quality gate + font fix | ✅ Committed (`c19cd9d`) |
| 8 | Track Record Quality | 5-signal 의미 매칭 + 37 테스트 | ✅ Committed (`98dac35`) |
| 9 | Presentation Quality | Evidence gate + domain slides + quality checks | ✅ Committed (`f1e72e5`) |
| 11 | User Trust | matched_signals + confidence UI | ✅ Committed (`98dac35`) |
| 12 | Recovery & Reliability | 재시도/이전버전/에러토스트/파일검증 | ✅ Committed (`98dac35`, `b956272`) |
| 15 | Security | P0 보안 4건 + rate limit + magic bytes + file type validation | ✅ Committed (`98dac35`, `b956272`) |

> **Note**: All 12 items are committed to `main` but NOT yet deployed to Railway production.

### 미완료 (5/17 → Phase 3)
| # | 요구사항 | Phase |
|---|---------|-------|
| 10 | Multi-Doc Relearn | 3A |
| 13 | Enterprise Collaboration | 3B |
| 14 | Operational Observability | 3B |
| 16 | Performance & Cost | 3C |
| 17 | Commercial Readiness | 3C |

### Open Issues (P1)
| # | 이슈 | 파일 | 상태 |
|---|------|------|------|
| P1-1 | upload-rfp rate limit 미적용 | studio.py | Open |
| ~~P1-2~~ | ~~계정 삭제 후 재로그인 시 org 재생성~~ | ~~deps.py~~ | Fixed in `36c3736` |
| ~~P1-5~~ | ~~신규 3개 엔드포인트 테스트 미작성~~ | ~~services/web_app/tests/~~ | Fixed in `b956272` |

### Phase 3 진입 조건
- [ ] RFP Stage 3개 신규 흐름 E2E 검증 (검색/업로드/분석→분류)
- [ ] Manual Override 실제 사용 검증
- [ ] Quality Gate 결과 사용자 이해 가능 확인
- [ ] 삭제/면제/복구/재시도 흐름 검증
- [ ] P0/P1 이슈 0건 확인 (P1-1 remaining)
- [x] 현재 배치 커밋 완료 (`98dac35`..`f1e72e5`, 5 commits on main)

### Rollback 포인트
- 배포 전 마지막 안정 커밋: `f0ef2a7` (refactor docs, 현재 프로덕션 상태)
- 신규 커밋 범위: `98dac35`..`f1e72e5` (5 commits, 아직 미배포)
- 프로덕션: Railway 자동 배포 — 이전 커밋으로 롤백 가능
- DB: 스키마 변경 없음 (안전)
