# Bid Studio — 전문가용 입찰 문서 생산 워크스페이스 구현 계획 v3

## 한 줄 정의

> Studio는 공고·회사 역량·스타일 자산을 학습시켜 제안서와 수행계획서를 반복 생성하고 개선하는 전문가용 워크스페이스다.

---

## Architecture Decision Records (ADR)

### ADR-1: CompanyDB 소유 범위

**결정: project-scoped staging → explicit promote**

```
Studio 프로젝트 내 입력 → project_company_assets (프로젝트 전용 staging)
  → 생성 시: staging 데이터 + shared CompanyDB 병합하여 사용
  → 사용자가 "회사 공용 DB에 반영" 클릭 시에만 shared CompanyDB에 promote
  → promote 안 하면 프로젝트 안에서만 사용
```

- Settings/Company의 shared CompanyDB는 오염 안 됨
- promote 시: audit trail (누가, 언제, 무엇을 승격)
- 동일 항목 충돌 시: 최신 우선, 충돌 경고 표시

### ADR-2: Chat → Studio 핸드오프 API

**결정: `POST /api/studio/projects` with optional `from_analysis_snapshot_id`**

```
POST /api/studio/projects
{
  "title": "치유농업 연구용역",
  "from_analysis_snapshot_id": "snap_abc123"   // optional
}
→ { "project_id": "proj_xyz", "studio_stage": "rfp" }
```

- snapshot 소유권 검증 (같은 org만)
- snapshot 미존재 시 404
- snapshot은 attach(복사)만, 원본 변경 안 함
- 빈 프로젝트 생성도 가능 (snapshot 없이)

### ADR-3: Studio canonical engine

**결정: 기존 orchestrators 직접 호출**

```
Studio API
  → build_company_context(shared CompanyDB + project staging)
  → load_style_skill(pinned version)
  → proposal_orchestrator.generate_proposal()
  → wbs_orchestrator.generate_wbs()
  → ppt_orchestrator.generate_ppt()
  → track_record_orchestrator.generate_track_record()
```

- 새 엔진 만들지 않음. 입력 소스만 달라짐 (session RAG → CompanyDB + style_skill)
- **결과**: wbs_planner.py 품질 문제(IT 하드코딩, 기간 파싱)는 Studio 정식 경로 품질 문제로 재분류 → Phase 5 prerequisite로 수정

### ADR-4: 스타일 스킬 소유 범위

**결정: 프로젝트가 특정 버전을 pin, 재학습은 새 버전 생성 + explicit promote**

```
style_skill v1 (회사 공용 기본, base_version)
  → 프로젝트 A: v1 pin → 재학습 → v2 생성 (derived_from=v1, 프로젝트 A 전용)
  → 프로젝트 B: v1 pin (v2 안 보임)
  → 사용자가 "v2를 회사 기본으로 승격" → shared base_version = v2
```

- `base_version`, `derived_from_version`, `promoted_at`, `promoted_by` 추적
- promote 패턴은 CompanyDB와 동일
- rollback: 이전 base_version으로 되돌리기 가능

---

## 제품 경계

| 영역 | 역할 | 라우트 |
|------|------|--------|
| **Chat** | 탐색: 공고 검색/분석, 일반 문서 분석, 알림, 예측, 회사 DB 상태 보기 | `/chat` |
| **Studio** | 프로젝트 scoped staging + 학습 + 생성 + 검토 + 재학습 (**정식 생성 경로**) | `/studio`, `/studio/projects/:id` |
| **Settings** | Shared master: 회사 공통 자산 정식 관리 | `/settings/company` |

### 마이그레이션 표

| 기능 | 현재 | 변경 |
|------|------|------|
| 공고 검색/분석 | Chat | **Chat 유지** |
| 일반 문서 분석 | Chat | **Chat 유지** |
| 공고 알림 | Chat/Alerts | **유지** |
| 발주 예측 | Chat/Forecast | **유지** |
| 회사 역량 DB 상태 | Chat | **Chat: 상태 + "Studio/Settings에서 관리" CTA** |
| 회사 역량 DB 편집 | Chat + Settings | **Settings = shared master, Studio = project staging** |
| 제안서 생성 | Chat 버튼 | **deprecated → Studio only** |
| 수행계획서 생성 | Chat 버튼 | **deprecated → Studio only** |
| PPT 생성 | Chat 버튼 | **deprecated → Studio only** |
| 실적기술서 생성 | Chat 버튼 | **deprecated → Studio only** |
| 수정/재학습 | 없음 | **Studio 전용** |

---

## 재사용 가능한 기존 자산

| 기존 모듈 | Studio에서 어떻게 쓰이나 |
|-----------|------------------------|
| `BidProject` (SQLAlchemy) | Studio 프로젝트 모델로 확장 |
| `AnalysisSnapshot` | 공고 분석 결과 (attach/복사) |
| `DocumentRun` / `Revision` / `Asset` | 생성 이력 |
| `CompanyDB` + `CompanyCapabilityProfile` | Shared master (read) + project staging (write) |
| `company_analyzer.analyze_company_style()` | 스타일 추출 |
| `company_profile_builder` + `profile.md` | 스타일 스킬 영속화 |
| `wbs_orchestrator` / `ppt_orchestrator` / `proposal_orchestrator` | 정식 생성기 (ADR-3) |
| `diff_tracker` + `auto_learner` | 수정 학습 파이프라인 |
| `quality_checker` | 생성 품질 검증 |

---

## 구현 Phase 분할

```
Phase 0: 전환 준비 ──────────────── Chat deprecated + 치명 버그 + ADR 확정
Phase 1: Studio 쉘 ──────────────── /studio + CRUD + Chat→Studio CTA
Phase 2: 공고 스테이지 ──────────── 입력/분석/핸드오프
Phase 3: 회사 역량 스테이지 ─────── project staging + shared DB 연동
Phase 4: 스타일 학습 스테이지 ───── 스킬 추출/pin/버전 관리
Phase 5: 생성 스테이지 ──────────── 생성기 품질 수정 + contract 투명성
Phase 6: 검토/재학습 스테이지 ───── diff 학습 + promote
Phase 7: 마무리 ─────────────────── HTML PPT, 통합 테스트, 레거시 정리, 배포
```

---

## Phase 0: 전환 준비

### Task 0-1: Chat 생성 버튼 deprecated

**파일:**
- `frontend/kirabot/components/chat/messages/AnalysisResultView.tsx`
- `frontend/kirabot/hooks/useConversationFlow.ts`

**변경:**
- 5개 생성 버튼 → "Studio에서 문서 생성하기" CTA 1개
- 문구: "입찰 문서는 Studio에서 생성합니다."
- CTA → `POST /api/studio/projects` (from_analysis_snapshot_id 포함) → `/studio/projects/:id`

### Task 0-2: 치명 버그 최소 수정

**범위**: Studio canonical engine이 재사용하는 공통 모듈의 치명 버그만.

- [ ] `wbs_planner.py`: total_months 안전 clamp `max(1, min(60))` (적용 완료)
- [ ] `_extract_project_duration()`: 기간 파싱 실패 원인 로그 추가 (rfx_result.project_period 값 확인)

**하지 않는 것**: IT 하드코딩 전면 제거는 Phase 5에서 처리 (ADR-3 결과)

---

## Phase 1: Studio 쉘

### Task 1-1: 프론트엔드 라우트 + 레이아웃

**파일 (신규):**
- `frontend/kirabot/pages/StudioHome.tsx`
- `frontend/kirabot/pages/StudioProject.tsx`
- `frontend/kirabot/components/studio/StudioLayout.tsx`
- `frontend/kirabot/components/studio/StageNav.tsx`
- `frontend/kirabot/components/studio/ProjectContextPanel.tsx`

**파일 (수정):**
- `frontend/kirabot/App.tsx` — `/studio` 라우트
- `frontend/kirabot/components/chat/Sidebar.tsx` — Studio 진입 링크

### Task 1-2: 백엔드 Studio 프로젝트 API

**파일:** `services/web_app/api/studio.py` (신규)

**엔드포인트:**
```
POST   /api/studio/projects                    — 생성 (from_analysis_snapshot_id optional)
GET    /api/studio/projects                    — 목록
GET    /api/studio/projects/:id                — 상세
PUT    /api/studio/projects/:id                — 수정
DELETE /api/studio/projects/:id                — 삭제
```

**생성 계약:**
```json
POST /api/studio/projects
{
  "title": "사업명",
  "from_analysis_snapshot_id": "snap_abc"  // optional, Chat 핸드오프 시
}
→ {
  "project_id": "proj_xyz",
  "studio_stage": "rfp",
  "rfp_attached": true
}
```
- `from_analysis_snapshot_id`: 같은 org 소유 확인, 미존재 시 404
- snapshot은 복사(attach), 원본 불변
- 초기 `studio_stage`: snapshot 있으면 "rfp" (완료), 없으면 "rfp" (미완료)

**모델 확장:**
- `BidProject`: `project_type` ("chat" | "studio"), `studio_stage` 추가

### Task 1-3: Chat → Studio 핸드오프

**파일:** `AnalysisResultView.tsx`

- 분석 완료 후: "이 공고로 Studio 프로젝트 시작" 버튼
- 클릭 → `POST /api/studio/projects` (snapshot attach) → 리다이렉트

---

## Phase 2: 공고 스테이지

### Task 2-1: 공고 입력 UI

**파일 (신규):**
- `frontend/kirabot/components/studio/stages/RfpStage.tsx`
- `RfpSearchPanel.tsx` / `RfpUploadPanel.tsx` / `RfpAnalysisView.tsx`

**기능:**
- 나라장터 검색 / 파일 업로드 / 텍스트 입력
- Chat 핸드오프: snapshot 있으면 자동 로드
- "공고 확정" → AnalysisSnapshot 저장 → stage 완료

### Task 2-2: 공고 API

```
POST /api/studio/projects/:id/rfp/analyze
GET  /api/studio/projects/:id/rfp
```

---

## Phase 3: 회사 역량 스테이지

### Task 3-1: 회사 역량 입력 UI

**파일 (신규):**
- `CompanyStage.tsx` / `CompanyDocUpload.tsx` / `CompanyProfileEditor.tsx` / `CompanyAssetList.tsx`

**기능:**
- 파일 업로드, 자연어 입력, 구조화 편집
- Shared CompanyDB에서 기존 자산 가져오기 (read)
- 새 입력 → **project staging** 저장 (shared DB 오염 안 함)
- "회사 공용 DB에 반영" 버튼 → **explicit promote** (audit trail)

### Task 3-2: 회사 역량 API

```
POST /api/studio/projects/:id/company/upload   — 파일 → project staging
POST /api/studio/projects/:id/company/text     — 텍스트 → project staging
GET  /api/studio/projects/:id/company          — staging + shared 병합 뷰
PUT  /api/studio/projects/:id/company/profile  — staging 편집
POST /api/studio/projects/:id/company/promote  — staging → shared CompanyDB 승격
```

**promote 규칙:**
- 승격 대상 선택 (전체 or 개별 항목)
- 동일 항목 충돌: 최신 우선 + 경고 표시
- audit: `promoted_by`, `promoted_at`, `source_project_id`

---

## Phase 4: 스타일 학습 스테이지

### Task 4-1: 스타일 학습 UI

**파일 (신규):**
- `StyleStage.tsx` / `StyleUpload.tsx` / `StylePreview.tsx` / `StyleSkillManager.tsx`

**기능:**
- 과거 제안서/수행계획서 업로드 → 스타일 추출
- 추출 결과 미리보기 (문체, 표현, 목차, 서식)
- "이 스타일 저장" → style_skill 새 버전 생성 (project-scoped)
- 기존 shared 스타일 가져오기 (pin)
- "회사 기본 스타일로 승격" → explicit promote

### Task 4-2: 스타일 API

```
POST /api/studio/projects/:id/style/analyze   — 분석 → StyleProfile
POST /api/studio/projects/:id/style/save      — → style_skill 저장 (project-scoped)
GET  /api/studio/projects/:id/style           — 현재 pinned 스타일
GET  /api/studio/projects/:id/style/history   — 버전 이력
POST /api/studio/projects/:id/style/promote   — 프로젝트 스타일 → shared 기본 승격
```

**버전 모델:**
```
style_skill:
  version: int
  base_version: int (shared 기본에서 파생 시)
  derived_from_version: int | null
  project_id: str | null (null = shared)
  promoted_at: datetime | null
  promoted_by: str | null
```

---

## Phase 5: 생성 스테이지

### Task 5-0: WBS/PPT 프롬프트 품질 수정 (Phase 5 prerequisite)

**근거**: ADR-3에서 기존 orchestrators를 정식 경로로 확정했으므로, 프롬프트 품질 문제는 Studio 품질 문제.

**파일:** `rag_engine/wbs_planner.py`

- [ ] 시스템 프롬프트: "IT 프로젝트 방법론 전문가" → "공공사업 수행계획 전문가"
- [ ] 방법론 감지: IT 프레임 제거, 사업 특성 기반 판단
- [ ] 템플릿: 강제 적용 → "참고 예시" 격하
- [ ] role: "PM/PL/개발자/QA/DBA" → "사업에 적합한 역할"
- [ ] 생성 지시: "이 사업의 특성에 맞는 단계/태스크를 직접 설계하세요"

**검증**: 치유농업 RFP → IT 단계 아닌 연구 단계 생성

### Task 5-1: 생성 UI

**파일 (신규):**
- `GenerateStage.tsx` / `GenerateContractView.tsx` / `GenerateRunList.tsx`

**기능:**
- 문서 타입 선택 (제안서/수행계획서/PPT/실적기술서)
- 생성 전 contract 투명성:
  - "공고: v1 ✓" / "회사: staging 5건 + shared 15건 ✓" / "스타일: v2 (pin) ✓"
  - 누락 경고
- "생성" → GenerationContract → DocumentRun

### Task 5-2: 생성 API

```
POST /api/studio/projects/:id/generate     — 생성 실행
GET  /api/studio/projects/:id/runs         — 이력
GET  /api/studio/projects/:id/runs/:runId  — 상세 (contract + result)
```

**내부 파이프라인:**
```
1. AnalysisSnapshot 로드 (프로젝트 공고)
2. CompanyDB context 빌드 (shared + project staging 병합)
3. style_skill 로드 (pinned version)
4. GenerationContract 기록 (입력 버전 스냅샷)
5. orchestrator 호출 (company_context + profile_md 주입)
6. DocumentRun + Revision + Asset 저장
```

---

## Phase 6: 검토/재학습

### Task 6-1: 검토 UI

**파일 (신규):**
- `ReviewStage.tsx` / `DocumentPreview.tsx` / `DiffView.tsx` / `RelearnDialog.tsx`

**기능:**
- 생성 결과 프리뷰 (DOCX 다운로드 + 웹)
- 수정본 업로드 or 웹 편집
- diff 시각화
- "이 수정을 학습할까요?" → style_skill 새 버전 (project-scoped)
- "회사 기본에도 반영?" → explicit promote

### Task 6-2: 재학습 API

```
POST /api/studio/projects/:id/feedback    — 수정본 업로드
GET  /api/studio/projects/:id/feedback    — 수정 이력
POST /api/studio/projects/:id/relearn     — diff → style_skill 새 버전
```

---

## Phase 7: 마무리

### Task 7-1: HTML PPT 프리뷰
- 설계: `docs/plans/2026-03-17-html-ppt-poc-design.md`

### Task 7-2: 전체 통합 테스트
- Studio E2E full cycle
- Chat 회귀 (검색/분석 + 생성 deprecated)

### Task 7-3: 레거시 정리
- Chat 생성 핸들러 완전 제거
- 레거시 generate-* 프록시 정리
- session RAG 회사 문서 경로 정리

### Task 7-4: 배포 + UX 검증

---

## 기존 시스템과의 관계

| 기존 | Studio에서 | 변경사항 |
|------|-----------|---------|
| Chat 생성 버튼 | Phase 0 deprecated | Phase 7 완전 제거 |
| session RAG | Chat 전용 유지 | Studio 사용 안 함 |
| CompanyDB | **shared master** (read) | Studio는 project staging + promote |
| profile.md / style_skill | **versioned + pinned** | project-scoped → promote |
| orchestrators | Studio 정식 생성기 | 프롬프트 품질 수정 (Phase 5) |
| Settings/Company | shared master 편집 | 변경 없음 |

---

## 완료 기준

1. `/studio` 접속 → 프로젝트 생성 → 5단계 full cycle
2. 공고 → 회사 역량 (staging) → 스타일 학습 (pin) → 생성 → 검토 → 재학습
3. 생성 결과에 회사 데이터 + 스타일 + 사업 특성 실제 반영
4. contract 투명성: "어떤 입력으로 생성됐는가" 표시
5. project staging이 shared CompanyDB를 오염시키지 않음
6. promote 시 audit trail 기록
7. Chat: 검색/분석 정상, 생성 → Studio CTA
8. 전체 테스트 green + 배포 정상

---

## 명시적으로 하지 않는 것

- ❌ session RAG 브리지 고도화
- ❌ Chat 생성 경로 품질 개선
- ❌ /settings/documents를 Studio로 통합
- ❌ document_orchestrator + pack 시스템으로 전환 (현 시점)
