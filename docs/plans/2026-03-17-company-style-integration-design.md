# 회사 스타일 분석 연결 — Staged B Migration 설계

## 1. 현재 상태 요약

### 두 개의 회사 컨텍스트 경로

```
경로 A: company_context (자동 빌드)
  CompanyDB.profile.writing_style → company_context_builder._format_style()
  CompanyDB.search_similar_projects() → _format_projects()
  CompanyDB.find_matching_personnel() → _format_personnel()
  → 마크다운 문자열 → section_writer "## 이 회사의 과거 제안서 스타일 및 역량"

경로 B: profile_md (파일 기반)
  data/company_skills/{company_id}/profile.md → 6개 섹션
  → section_writer "## 이 회사의 제안서 프로필 (반드시 준수)"
```

### profile_md 소비자 전수 조사

| 계층 | 소비자 | 유형 | 수 |
|------|--------|------|---|
| **프론트엔드 UI** | ProfileEditor.tsx (WYSIWYG 편집) | 외부 | 1 |
| **프론트엔드 API** | kiraApiService.ts (4개 함수) | 외부 | 4 |
| **web_app 프록시** | /api/profile-md (GET/PUT/GET history/POST rollback) | 외부 | 4 |
| **rag_engine API** | /api/company-profile/* (8개 엔드포인트) | 외부 | 8 |
| **생성 오케스트레이터** | proposal/ppt/wbs/track_record orchestrator | 내부 | 4 |
| **섹션 라이터** | section_writer.py (프롬프트 주입) | 내부 | 1 |
| **테스트** | test_profile_api.py, test_profile_md_api.py | 테스트 | 10+ |

### 핵심 발견

**profile_md는 단순 내부 배관이 아닙니다.**

사용자가 직접 편집하는 6개 섹션 WYSIWYG 에디터(ProfileEditor.tsx)가 있고,
버전 관리(changelog.json) + 롤백 기능까지 있습니다. 이건 사용자 대면 기능입니다.

반면 company_context는 CompanyDB에서 매 생성 시 자동 빌드되는 ephemeral 문자열입니다.

**두 경로의 역할이 다릅니다:**
- `company_context`: 구조화된 데이터에서 자동 조립 (실적, 인력, writing_style)
- `profile_md`: 사용자가 직접 큐레이션한 회사 DNA (톤, 강점 표현, 평가전략)

---

## 2. 접근 비교

### A. 현 구조 유지 + profile.md 자동 재생성

| 항목 | 평가 |
|------|------|
| **변경 범위** | 최소 (main.py 1곳, 3줄) |
| **회귀 위험** | 거의 없음 |
| **해결하는 문제** | writing_style → profile.md 동기화 |
| **해결 못 하는 문제** | 두 경로 중복 주입 (LLM 프롬프트에 비슷한 내용 2번 들어감) |
| **롤백 용이성** | 매우 쉬움 |
| **디버그 난이도** | 낮음 |

**장점**: 기존 사용자 기능(WYSIWYG 편집, 버전 관리) 100% 보존
**단점**: 근본적으로 두 source가 drift할 수 있는 구조 유지

### B1. Staged B — read-path 통일, profile.md는 deprecated/generated

| 항목 | 평가 |
|------|------|
| **변경 범위** | 중간 (8+ 파일, read abstraction 도입) |
| **회귀 위험** | 중간 (프롬프트 품질 변경) |
| **해결하는 문제** | 단일 source of truth, 프롬프트 중복 제거 |
| **해결 못 하는 문제** | 프론트엔드 ProfileEditor 대체 필요 |
| **롤백 용이성** | 중간 (read abstraction 제거로 롤백 가능) |
| **디버그 난이도** | 중간 |

**장점**: company_context가 유일한 진실
**단점**: ProfileEditor.tsx가 현재 profile.md 파일을 직접 CRUD — 대체 UI 필요.
사용자가 "톤을 격식체로 바꿔줘" 같은 수동 편집을 하던 기능이 사라짐.

### B2. Big bang B — profile.md + CRUD/API 한 번에 제거

| 항목 | 평가 |
|------|------|
| **변경 범위** | 대형 (20+ 파일, API 삭제, UI 교체) |
| **회귀 위험** | 높음 (사용자 대면 기능 삭제) |
| **해결하는 문제** | 완전한 단일 source |
| **해결 못 하는 문제** | - |
| **롤백 용이성** | 어려움 |
| **디버그 난이도** | 높음 |

**장점**: 깔끔
**단점**: 사용자 기능 파괴. ProfileEditor.tsx 즉사. 12개 API 엔드포인트 삭제 필요.

---

## 3. 추천안 + 이유

### 추천: **A + α** (현 구조 유지 + 동기화 + 중복 제거)

**staged B가 아닌 A+α를 추천하는 이유:**

탐색 결과, profile_md는 "내부 배관"이 아니라 **사용자가 직접 편집하는 제품 기능**입니다.

- ProfileEditor.tsx WYSIWYG 에디터 존재
- 버전 관리 + 롤백 기능 존재
- 8개 CRUD API + 4개 프록시 + 4개 프론트엔드 함수

이 상태에서 staged B를 하면:
1. ProfileEditor를 CompanyDB 기반으로 재작성해야 함 (structured editor)
2. 버전 관리/롤백을 CompanyDB 레벨로 이관해야 함
3. 12개 API를 교체/폐기해야 함

**이건 "회사 스타일 분석 연결"이 아니라 "프로필 편집 시스템 재작성"입니다.**

### A+α가 해결하는 것

1. **끊어진 연결 수리**: analyze_company_style() → profile.md 자동 갱신
2. **프롬프트 중복 제거**: section_writer에서 profile_md + company_context 중 하나만 주입
3. **사용자 기능 100% 보존**: ProfileEditor, 버전 관리, 롤백 모두 유지

### 오너십 판단 근거

- "깔끔해 보이는 변경"(B)보다 "회귀 없이 실질 문제를 해결"(A+α)이 오너십
- staged B의 1단계(read abstraction)만 해도 8개 파일 변경, ProfileEditor 대체 설계 필요
- 현재 실질 문제는 "profile.md가 존재한다"가 아니라 "writing_style이 profile.md에 동기화 안 된다"
- 그 문제는 3줄로 고칠 수 있음

---

## 4. A+α 설계

### 목표

1. writing_style 분석 → profile.md 자동 갱신 (끊어진 연결 수리)
2. LLM 프롬프트에서 company_context와 profile_md 중복 주입 정리
3. 기존 사용자 기능 (편집, 버전관리, 롤백) 100% 보존

### Source of Truth 정의

```
writing_style 데이터:
  Source of Truth: CompanyDB.profile.writing_style (dict)
  Derived View: profile.md 파일 (build_profile_md()로 생성)

회사 역량 데이터:
  Source of Truth: CompanyDB (실적, 인력, 프로필)
  Derived View: company_context 문자열 (매 생성 시 빌드)

사용자 편집:
  Source of Truth: profile.md 파일 (직접 편집 가능)
  → 사용자가 수동 편집하면 profile.md가 CompanyDB보다 우선
```

### Target Architecture

```
analyze_company_style() 호출 시:
  1. StyleProfile → CompanyDB.profile.writing_style 저장 (기존)
  2. StyleProfile → build_profile_md() → save_profile_md() (NEW: 자동 갱신)

생성 파이프라인 (proposal/ppt/wbs/track_record):
  1. company_context = build_company_context() (실적+인력+writing_style)
  2. profile_md = load_profile_md() (사용자 큐레이션 DNA)
  3. section_writer: company_context에서 writing_style 섹션 제거 (중복 방지)
     → profile_md에 이미 같은 내용이 있으므로 company_context에서는 빼기
```

---

## 5. 구현 계획

### Task 1: analyze_company_style() → profile.md 자동 갱신

**Files:**
- `rag_engine/main.py` (line 1442-1462, /api/analyze-company-style endpoint)

**Step 1: Failing test**
```python
# tests/test_company_style_sync.py
def test_analyze_style_updates_profile_md():
    """analyze-company-style 호출 후 profile.md가 자동 갱신되는지 확인"""
    # 1. analyze-company-style 호출
    # 2. load_profile_md() 결과에 writing_style 내용이 반영됐는지 확인
    # 3. "격식체" 등 StyleProfile 내용이 profile.md에 포함되는지 확인
```

**Step 2: Run test and confirm fail** (profile.md 갱신 안 됨)

**Step 3: Minimal implementation**
```python
# main.py, /api/analyze-company-style endpoint 끝부분 (line ~1460)
# 기존: CompanyDB.save_profile() 후 종료
# 추가: profile.md 자동 갱신
from company_profile_builder import build_profile_md, save_profile_md
skills_dir = _get_company_skills_dir(req.company_id)
if skills_dir:
    profile_md = build_profile_md(
        company_name=profile.name if profile else "미설정",
        style=style,
    )
    save_profile_md(skills_dir, profile_md)
```

**Step 4: Run tests and confirm pass**
**Step 5: Commit** — `fix(company-style): auto-sync StyleProfile to profile.md after analysis`

---

### Task 2: company_context에서 writing_style 중복 제거

**Files:**
- `rag_engine/company_context_builder.py` (_format_style 함수)

**Step 1: Failing test**
```python
# tests/test_company_context_builder.py
def test_build_company_context_excludes_writing_style_when_profile_md_exists():
    """profile_md가 있으면 company_context에서 writing_style 섹션을 빼는지 확인"""
    # build_company_context(rfx_result, ..., skip_writing_style=True)
    # 결과에 "과거 제안서 스타일" 섹션이 없어야 함
```

**Step 2: Run test and confirm fail**

**Step 3: Minimal implementation**
```python
# company_context_builder.py
def build_company_context(rfx_result, ..., skip_writing_style: bool = False) -> str:
    # ... existing code ...
    if not skip_writing_style:
        style_section = _format_style(profile.writing_style if profile else {})
        if style_section:
            sections.append(style_section)
```

**Step 4: Run tests and confirm pass**
**Step 5: Commit** — `refactor(context-builder): add skip_writing_style flag to prevent prompt duplication`

---

### Task 3: 오케스트레이터에서 중복 방지 적용

**Files:**
- `rag_engine/proposal_orchestrator.py`
- `rag_engine/ppt_orchestrator.py`
- `rag_engine/wbs_orchestrator.py`
- `rag_engine/track_record_orchestrator.py`

**Step 1: Failing test**
```python
# tests/test_prompt_deduplication.py
def test_proposal_orchestrator_skips_writing_style_in_context_when_profile_md_present():
    """profile_md가 있으면 company_context에 writing_style이 중복으로 들어가지 않는지"""
```

**Step 2: Run test and confirm fail**

**Step 3: Minimal implementation**
각 오케스트레이터의 build_company_context() 호출에 `skip_writing_style=True` 추가
(profile_md를 로드하는 경우에만):
```python
# 4개 오케스트레이터 공통 패턴
profile_md = ""
if company_skills_dir:
    profile_md = load_profile_md(company_skills_dir)

company_context = build_company_context(
    rfx_result, ...,
    skip_writing_style=bool(profile_md),  # profile_md가 있으면 중복 방지
)
```

**Step 4: Run tests and confirm pass**
**Step 5: Commit** — `fix(orchestrators): deduplicate writing_style between company_context and profile_md`

---

### Task 4: 전체 회귀 테스트

**Step 1: rag_engine 전체** `python -m pytest -q` (391+ passed)
**Step 2: web_app 전체** `BID_TEST_DATABASE_URL=... python -m pytest services/web_app/tests -q`
**Step 3: root legacy** `python -m pytest tests -q`
**Step 4: frontend** `npx tsc --noEmit`

---

## 6. 위험요소 / 롤백 / 관측

### 위험요소

| 리스크 | 확률 | 영향 | 완화 |
|--------|------|------|------|
| profile.md 자동 갱신이 사용자 수동 편집을 덮어씀 | 중 | 높 | 사용자가 수동 편집한 profile.md가 있으면 자동 갱신 skip |
| skip_writing_style로 프롬프트 품질 저하 | 낮 | 중 | profile_md가 비어있으면 skip 안 함 |
| build_profile_md() 실패로 분석 API 전체 실패 | 낮 | 높 | try/except + 로깅 (분석은 성공, 갱신은 best-effort) |

### 롤백 전략

- Task 1: main.py에서 3줄 제거 → profile.md 자동 갱신 중단
- Task 2: skip_writing_style 파라미터 기본값 False → 이전 동작 복원
- Task 3: bool(profile_md) → False로 변경 → 이전 동작 복원

각 Task가 독립적이므로 개별 롤백 가능.

### 관측 전략

```python
# main.py, analyze-company-style endpoint
logger.info(
    "company_style_synced_to_profile_md",
    company_id=req.company_id,
    style_tone=style.tone,
    profile_md_updated=True,
)
```

---

## 7. 완료 선언 기준

1. `analyze_company_style()` 호출 후 `load_profile_md()`가 writing_style 내용을 포함
2. 생성 파이프라인에서 writing_style이 프롬프트에 1번만 주입됨 (중복 없음)
3. ProfileEditor.tsx 정상 동작 (편집, 버전 관리, 롤백)
4. 전체 회귀 646+ tests passing
5. 기존에 수동 편집된 profile.md는 보존됨 (덮어쓰기 방지)

---

## Staged B 재평가 시점

A+α가 완료된 후, 다음 조건이 모두 충족되면 staged B를 재검토:
- CompanyDB에 구조화된 프로필 편집 UI가 생김
- ProfileEditor.tsx를 CompanyDB 기반으로 교체할 제품 요구사항이 나옴
- profile.md 파일 의존 경로가 0개가 됨

**그때까지는 profile_md가 "사용자 편집 가능한 derived view"로서 정당한 존재입니다.**
