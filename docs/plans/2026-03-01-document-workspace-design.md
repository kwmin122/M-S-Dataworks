# Document Workspace — 문서 편집 워크스페이스 설계

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 사용자가 profile.md, RFP 분석결과, 생성 문서(제안서/WBS/PPT)를 웹에서 직접 편집하고, 외부 편집본을 업로드하여 학습시키는 통합 문서 워크스페이스.

**Architecture:** Settings 페이지의 `/settings/documents` 탭에 문서 워크스페이스를 배치. 왼쪽 탭 네비게이션(프로필/RFP/제안서/WBS/PPT) + 오른쪽 편집영역. 채팅에서 [편집] 버튼으로 직접 진입 가능. 모든 편집은 diff_tracker → auto_learner로 연결되어 수정이 곧 학습.

**Tech Stack:** React 19 + TypeScript + Tailwind + Lucide icons (프론트), FastAPI + Python (백엔드), 기존 company_profile_updater/diff_tracker/auto_learner 재활용.

---

## 라우팅

```
/settings/documents          ← 신규 탭
  ?tab=profile                 회사 프로필 (profile.md)
  ?tab=rfp                     RFP 분석결과
  ?tab=proposal&id=xxx         제안서 편집
  ?tab=wbs&id=xxx              WBS 편집
  ?tab=ppt&id=xxx              PPT 편집
```

채팅 진입: `[편집]` 버튼 → `/settings/documents?tab=proposal&id=xxx`

## 편집 UX

### profile.md
- 6개 섹션을 카드로 표시 (문서스타일, 문체, 강점, 전략, HWPX규칙, 학습이력)
- 섹션별 [편집] → 마크다운 텍스트에어리어 전환 → [저장]/[취소]
- 학습 이력은 읽기전용
- 버전 히스토리 타임라인 + 롤백

### RFP 분석결과
- 자격요건: 리스트 편집 (추가/삭제/수정)
- 평가기준: 테이블 편집
- RFP 요약: 마크다운 편집기
- [저장하고 재생성에 반영] 버튼

### 생성 문서 (제안서/WBS/PPT)
- 하이브리드: 웹 인라인 편집 + 파일 업로드
- 웹 편집: 섹션별 마크다운 텍스트에어리어
- 파일 업로드: 원본 다운로드 → 외부 편집 → 수정본 드래그&드롭 → 자동 diff + 학습
- [재다운로드] [재생성] 버튼

## API 설계

### Profile.md
- `GET /api/company-profile/md` → sections + metadata
- `PUT /api/company-profile/md/section` → update section + auto backup
- `GET /api/company-profile/md/history` → version list
- `POST /api/company-profile/md/rollback` → restore version

### RFP 분석결과
- `GET /api/rfp-analysis/latest?session_id=xxx`
- `PUT /api/rfp-analysis/update`

### 생성 문서
- `GET /api/documents/list?session_id=xxx`
- `GET /api/documents/{doc_id}/sections`
- `PUT /api/documents/{doc_id}/section` → diff + learn
- `POST /api/documents/{doc_id}/upload-revision` → diff + learn
- `POST /api/documents/{doc_id}/regenerate`

## 컴포넌트 구조

```
components/settings/documents/
├── DocumentWorkspace.tsx     메인 레이아웃
├── DocumentTabNav.tsx        왼쪽 탭
├── ProfileEditor.tsx         profile.md 편집
├── ProfileSection.tsx        개별 섹션 카드
├── RfpEditor.tsx             RFP 편집
├── RequirementEditor.tsx     자격요건 리스트
├── ProposalEditor.tsx        제안서 편집
├── WbsEditor.tsx             WBS 편집
├── PptEditor.tsx             PPT 편집
├── DocumentSection.tsx       공통 마크다운 섹션
├── FileUploadZone.tsx        수정본 업로드
├── VersionHistory.tsx        버전 타임라인
└── DiffPreview.tsx           diff 미리보기
```

## 구현 Phase

| Phase | 범위 |
|-------|------|
| P1 | profile.md API + ProfileEditor + VersionHistory |
| P2 | RFP 분석결과 API + RfpEditor |
| P3 | 제안서 웹 편집 API + ProposalEditor |
| P4 | 파일 업로드 학습 API + FileUploadZone + DiffPreview |
| P5 | WBS/PPT 편집 (P3 패턴 재사용) |
| P6 | 채팅 [편집] 버튼 연동 |

## 데이터 플로우

모든 편집 경로 → `diff_tracker.extract_diff()` → `auto_learner.process_edit_feedback()` → 3회+ 패턴 시 profile.md 자동 업데이트.
