# Bid Studio — 구현 계획 v4

## 한 줄 정의

> Studio는 공고·회사 역량·스타일 자산을 학습시켜 제안서와 수행계획서를 반복 생성하고 개선하는 전문가용 워크스페이스다.

---

## ADR (Architecture Decision Records)

### ADR-1: CompanyDB 소유 범위

**결정: project-scoped staging → explicit promote**

- Studio 프로젝트 입력 → `project_company_assets` 테이블 (프로젝트 전용)
- 생성 시: staging + shared CompanyDB 병합
- "회사 공용 DB에 반영" 클릭 → shared CompanyDB에 promote (audit trail)
- promote 안 하면 프로젝트 안에서만

### ADR-2: Chat → Studio 핸드오프

**결정: `POST /api/studio/projects` + `from_analysis_snapshot_id` (clone semantics)**

- snapshot을 **clone** (새 row 생성, 원본 불변, 새 project에 바인딩)
- 원본 snapshot의 org 소유권 검증
- 미존재 시 404
- clone된 snapshot은 Studio 프로젝트 전용 (원본 프로젝트에 영향 없음)

### ADR-3: Studio canonical engine

**결정: 기존 orchestrators 직접 호출**

- wbs/ppt/proposal/track_record orchestrator 재사용
- 입력 소스만 변경: session RAG → (shared CompanyDB + project staging + pinned style_skill)
- **결과**: orchestrator 프롬프트 품질 문제(IT 하드코딩 등)는 Studio 정식 품질 문제 → Phase 5 prerequisite

### ADR-4: 스타일 스킬 소유 범위

**결정: project pin + derive + explicit promote**

- 프로젝트가 shared 기본 버전을 pin
- 재학습 → 새 버전 (project-scoped, `derived_from` 기록)
- "회사 기본으로 승격" → explicit promote
- rollback: 이전 shared 기본으로 복원 가능

---

## 저장 모델 스키마

### project_company_assets (신규 테이블)

```sql
CREATE TABLE project_company_assets (
    id          TEXT PRIMARY KEY,           -- cuid
    project_id  TEXT NOT NULL REFERENCES bid_projects(id) ON DELETE CASCADE,
    org_id      TEXT NOT NULL REFERENCES organizations(id),
    asset_type  TEXT NOT NULL,              -- 'track_record' | 'personnel' | 'technology' | 'certification' | 'raw_text'
    content     JSONB NOT NULL,             -- 구조화된 자산 데이터
    source_file TEXT,                       -- 원본 파일명 (있으면)
    promoted_at TIMESTAMPTZ,               -- shared DB 승격 시각 (null = 미승격)
    promoted_by TEXT,                       -- 승격 실행자
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pca_project ON project_company_assets(project_id);
```

### project_style_skills (신규 테이블)

```sql
CREATE TABLE project_style_skills (
    id                    TEXT PRIMARY KEY,      -- cuid
    project_id            TEXT REFERENCES bid_projects(id) ON DELETE CASCADE,  -- null = shared
    org_id                TEXT NOT NULL REFERENCES organizations(id),
    version               INT NOT NULL DEFAULT 1,
    derived_from_id       TEXT REFERENCES project_style_skills(id),  -- 파생 원본
    style_json            JSONB NOT NULL,        -- StyleProfile as JSON
    profile_md_content    TEXT,                   -- 렌더링된 profile.md 내용
    is_shared_default     BOOLEAN DEFAULT FALSE,  -- 회사 공용 기본 여부
    promoted_at           TIMESTAMPTZ,
    promoted_by           TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 프로젝트 내 버전 중복 방지
    UNIQUE (project_id, version)
);
-- org별 공용 기본은 정확히 1개만
CREATE UNIQUE INDEX idx_pss_shared_default ON project_style_skills(org_id) WHERE is_shared_default = true;
CREATE INDEX idx_pss_project ON project_style_skills(project_id);
```

### studio_analysis_snapshots (clone 관계)

AnalysisSnapshot 테이블은 기존 그대로 사용. clone 시:
```sql
-- 원본 snapshot을 복사해서 새 project에 바인딩
INSERT INTO analysis_snapshots (id, org_id, project_id, version, analysis_json, ...)
SELECT new_cuid(), org_id, :new_project_id, 1, analysis_json, ...
FROM analysis_snapshots WHERE id = :source_snapshot_id AND org_id = :org_id;
```
- 새 id 발급 (원본 불변)
- 새 project_id 바인딩
- version = 1 (새 프로젝트 기준)

---

## 제품 경계

| 영역 | 역할 | 라우트 |
|------|------|--------|
| **Chat** | 탐색: 검색/분석/질문/알림/예측/회사 DB 상태 | `/chat` |
| **Studio** | 프로젝트 staging + 학습 + 생성 + 검토 + 재학습 | `/studio`, `/studio/projects/:id` |
| **Settings** | Shared master: 회사 공통 자산 관리 | `/settings/company` |

### 마이그레이션 표

| 기능 | 현재 | 변경 |
|------|------|------|
| 공고 검색/분석 | Chat | Chat 유지 |
| 일반 문서 분석 | Chat | Chat 유지 |
| 알림/예측 | Chat | 유지 |
| 회사 DB 상태 | Chat | Chat: 상태 + CTA |
| 회사 DB 편집 | Chat+Settings | Settings=master, Studio=staging |
| **제안서 생성** | Chat 버튼 | **Phase 1 이후 feature flag → Studio CTA** |
| **수행계획서 생성** | Chat 버튼 | **Phase 1 이후 feature flag → Studio CTA** |
| **PPT 생성** | Chat 버튼 | **Phase 1 이후 feature flag → Studio CTA** |
| **실적기술서 생성** | Chat 버튼 | **Phase 1 이후 feature flag → Studio CTA** |
| 수정/재학습 | 없음 | Studio 전용 |

**중요**: Chat 생성 버튼은 Studio가 동작한 **후에** feature flag로 전환. Phase 0에서 내리지 않음.

---

## 구현 Phase

```
Phase 0: 치명 버그 + ADR 확정 커밋
Phase 1: Studio 쉘 + Chat→Studio CTA (이후 feature flag 전환)
Phase 2: 공고 스테이지
Phase 3: 회사 역량 스테이지 (staging + promote)
Phase 4: 스타일 학습 (pin + version + promote)
Phase 5: 생성 (품질 prerequisite + contract 투명성)
Phase 6: 검토/재학습
Phase 7: 마무리 (HTML PPT, 테스트, 레거시 정리, 배포)
```

---

## Phase 0: 치명 버그 + ADR 확정

### Task 0-1: 치명 버그 최소 수정

- [ ] `wbs_planner.py`: total_months clamp (적용 완료)
- [ ] `_extract_project_duration()`: 파싱 실패 로그 추가

### Task 0-2: ADR 문서 커밋

- [ ] 이 문서 (v4) 커밋
- [ ] 저장 모델 스키마 확정

**하지 않는 것**: Chat 생성 버튼 제거 (Studio가 동작한 후에)

---

## Phase 1: Studio 쉘 + feature flag

### Task 1-1: 프론트엔드 /studio 라우트

**신규:** `StudioHome.tsx`, `StudioProject.tsx`, `StudioLayout.tsx`, `StageNav.tsx`, `ProjectContextPanel.tsx`
**수정:** `App.tsx` (라우트), `Sidebar.tsx` (진입 링크)

### Task 1-2: 백엔드 Studio 프로젝트 API

**신규:** `services/web_app/api/studio.py`

```
POST   /api/studio/projects              — 생성 (from_analysis_snapshot_id로 clone)
GET    /api/studio/projects              — 목록
GET    /api/studio/projects/:id          — 상세
PUT    /api/studio/projects/:id          — 수정
DELETE /api/studio/projects/:id          — 삭제
```

**생성 계약:**
```json
POST /api/studio/projects
{
  "title": "사업명",
  "from_analysis_snapshot_id": "snap_abc"  // optional, clone semantics
}
→ {
  "project_id": "proj_xyz",
  "studio_stage": "rfp",
  "rfp_snapshot_cloned": true
}
```

clone 시: 새 AnalysisSnapshot row 생성, 원본 불변, 새 project에 바인딩.

### Task 1-3: Chat → Studio CTA + feature flag

**수정:** `AnalysisResultView.tsx`

- 분석 완료 후: "이 공고로 Studio 프로젝트 시작" 버튼 **추가** (기존 생성 버튼과 공존)
- `STUDIO_ENABLED` feature flag: true면 생성 버튼 숨기고 Studio CTA만 표시
- Phase 1 시점: flag = false (양쪽 공존). Studio 안정화 후 true로 전환.

### Task 1-4: DB 마이그레이션

**신규:** Alembic migration

- `bid_projects`: `project_type` ("chat" | "studio"), `studio_stage`, `pinned_style_skill_id` (FK → project_style_skills) 추가
- `project_company_assets` 테이블 생성
- `project_style_skills` 테이블 생성 (UNIQUE constraints 포함)

---

## Phase 2: 공고 스테이지

### Task 2-1: UI

`RfpStage.tsx`, `RfpSearchPanel.tsx`, `RfpUploadPanel.tsx`, `RfpAnalysisView.tsx`

- 나라장터 검색 / 파일 업로드 / 텍스트 입력
- clone된 snapshot 있으면 자동 로드
- "공고 확정" → snapshot 저장

### Task 2-2: API

```
POST /api/studio/projects/:id/rfp/analyze
GET  /api/studio/projects/:id/rfp
```

---

## Phase 3: 회사 역량 스테이지

### Task 3-1: UI

`CompanyStage.tsx`, `CompanyDocUpload.tsx`, `CompanyProfileEditor.tsx`, `CompanyAssetList.tsx`

- 파일/텍스트 입력 → **project_company_assets** 저장 (staging)
- shared CompanyDB 기존 자산 가져오기 (read)
- 병합 뷰: staging + shared
- "회사 공용 DB에 반영" → **promote** (감사 기록)

### Task 3-2: API

```
POST /api/studio/projects/:id/company/upload   — → project_company_assets
POST /api/studio/projects/:id/company/text     — → project_company_assets
GET  /api/studio/projects/:id/company          — staging + shared 병합 뷰
PUT  /api/studio/projects/:id/company/:assetId — staging 편집
POST /api/studio/projects/:id/company/promote  — staging → shared (선택적)
```

---

## Phase 4: 스타일 학습

### Task 4-1: UI

`StyleStage.tsx`, `StyleUpload.tsx`, `StylePreview.tsx`, `StyleSkillManager.tsx`

- 과거 제안서 업로드 → 스타일 추출
- shared 기본 스타일 pin / 새 버전 생성 (project-scoped)
- 버전 이력 관리
- "회사 기본으로 승격" → promote

### Task 4-2: API

```
POST /api/studio/projects/:id/style/analyze   — → StyleProfile
POST /api/studio/projects/:id/style/save      — → project_style_skills row
GET  /api/studio/projects/:id/style           — pinned 스타일
GET  /api/studio/projects/:id/style/versions  — 버전 이력
POST /api/studio/projects/:id/style/promote   — → is_shared_default = true
```

---

## Phase 5: 생성

### Task 5-0: 생성기 품질 prerequisite

**WBS** (`wbs_planner.py`):
- [ ] "IT 프로젝트 전문가" → "공공사업 수행계획 전문가"
- [ ] 방법론 감지: IT 프레임 제거
- [ ] 템플릿: "참고 예시" 격하
- [ ] role: 자유형
- [ ] 검증: 치유농업 RFP → 연구 단계 생성

**제안서** (`proposal_orchestrator.py`, `section_writer.py`):
- [ ] section_writer 프롬프트에 company_context가 실제 영향 주는지 검증
- [ ] 회사 실적/강점이 섹션 내용에 반영되는지 확인
- [ ] 검증: 회사 데이터 있을 때 vs 없을 때 결과 비교

**PPT** (`ppt_slide_planner.py`, `ppt_content_extractor.py`):
- [ ] IT 편향 프롬프트 확인 + 수정
- [ ] 사업 특성 반영 검증

### Task 5-1: 생성 UI

`GenerateStage.tsx`, `GenerateContractView.tsx`, `GenerateRunList.tsx`

- 문서 타입 선택
- contract 투명성: 사용된 입력 버전 표시
- 누락 경고

### Task 5-2: 생성 API

```
POST /api/studio/projects/:id/generate
GET  /api/studio/projects/:id/runs
GET  /api/studio/projects/:id/runs/:runId
```

**파이프라인:**
```
1. AnalysisSnapshot 로드
2. company_context 빌드 (shared CompanyDB + project staging 병합)
3. style_skill 로드 (pinned version → profile_md_content)
4. GenerationContract 기록
5. orchestrator 호출
6. DocumentRun + Revision + Asset 저장
```

---

## Phase 6: 검토/재학습

### Task 6-1: UI

`ReviewStage.tsx`, `DocumentPreview.tsx`, `DiffView.tsx`, `RelearnDialog.tsx`

### Task 6-2: API

```
POST /api/studio/projects/:id/feedback
GET  /api/studio/projects/:id/feedback
POST /api/studio/projects/:id/relearn     — diff → style_skill 새 버전
```

---

## Phase 7: 마무리

- Task 7-1: HTML PPT 프리뷰
- Task 7-2: 전체 통합 테스트
- Task 7-3: feature flag → true (Chat 생성 버튼 숨김, Studio CTA only)
- Task 7-4: Chat 회사 DB 편집 surface 축소 → 상태 보기 + "Settings/Studio에서 관리" CTA만 남김
- Task 7-5: 레거시 정리 (Chat 생성 핸들러, 프록시 API, session RAG 회사 경로)
- Task 7-6: 배포 + 실제 공고 3건 full cycle

---

## 완료 기준

1. `/studio` full cycle: 공고 → 회사(staging) → 스타일(pin) → 생성 → 검토 → 재학습
2. 생성 결과에 회사+스타일+사업 특성 실제 반영
3. contract 투명성: "어떤 입력 버전으로 생성됐는가"
4. staging이 shared DB를 오염시키지 않음
5. promote 시 audit trail
6. Chat: 검색/분석 정상, feature flag로 생성 CTA 전환
7. 전체 테스트 green + 배포

## 하지 않는 것

- ❌ Phase 0에서 Chat 생성 버튼 제거 (Studio 동작 후 feature flag)
- ❌ session RAG 브리지 고도화
- ❌ Chat 레거시 생성 경로 품질 개선
- ❌ document_orchestrator + pack 전환 (현 시점)
