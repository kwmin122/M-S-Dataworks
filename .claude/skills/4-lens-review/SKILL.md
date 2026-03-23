# 4-Lens Review (4팀 병렬)

코드 작업 완료 후 자동으로 실행하는 4-관점 통합 리뷰.
**4개 에이전트를 병렬로 dispatch**하여 각 관점에서 독립적으로 깊이 있게 분석한다.

## 언제 실행

**필수:**
- 코드 작업(Task) 완료 후, 다음 Task로 넘어가기 전
- 커밋 직후
- PR 생성 전

## 실행 방법

### 1단계: Git 범위 확인

```bash
BASE_SHA=$(git log --oneline -10 | grep -v "$(git rev-parse --short HEAD)" | head -1 | awk '{print $1}')
HEAD_SHA=$(git rev-parse --short HEAD)
git diff --stat ${BASE_SHA}..${HEAD_SHA}
```

### 2단계: 4개 에이전트 병렬 dispatch

**반드시 하나의 메시지에서 4개 Agent tool call을 동시에** 보내야 한다.
각 에이전트는 `superpowers:code-reviewer` 타입으로, 하나의 렌즈만 담당한다.

#### Agent 1: Code Review (코드리뷰)

```
name: review-code
subagent_type: superpowers:code-reviewer
prompt: |
  You are Lens 1: CODE REVIEW for {WHAT_WAS_IMPLEMENTED}.
  Git range: {BASE_SHA}..{HEAD_SHA}

  Focus ONLY on:
  - 버그 / 로직 오류
  - 권한 / 보안 (IDOR, injection, auth bypass, data leakage)
  - 회귀 리스크 (기존 기능이 깨지는가)
  - 테스트 갭 (테스트가 실제 로직을 검증하는가, mock만 테스트하지 않는가)
  - 잘못된 완료 선언 여부 ("All clean" 표현이 증거와 맞는가)

  Output: Findings (severity순, file:line 기준) + 좋은점 + 리스크
```

#### Agent 2: Developer (개발자 관점)

```
name: review-dev
subagent_type: superpowers:code-reviewer
prompt: |
  You are Lens 2: DEVELOPER REVIEW for {WHAT_WAS_IMPLEMENTED}.
  Git range: {BASE_SHA}..{HEAD_SHA}

  Focus ONLY on:
  - 스키마 / 계약 일관성 (DB 모델, API 인터페이스, 타입 정의가 서로 맞는가)
  - 마이그레이션 안전성 (rollback 가능한가, 기존 데이터와 호환되는가)
  - API / 프론트 경계 (백엔드 응답과 프론트 타입이 일치하는가)
  - 기술 부채 (지금 넘기면 나중에 더 비싸지는 것이 있는가)
  - 다음 task로 넘어가도 되는지 (선행 조건이 충족되었는가)

  Output: Findings (severity순, file:line 기준) + 좋은점 + 리스크
```

#### Agent 3: Owner-Operator (오너십 관점)

```
name: review-owner
subagent_type: superpowers:code-reviewer
prompt: |
  You are Lens 3: OWNER-OPERATOR REVIEW for {WHAT_WAS_IMPLEMENTED}.
  Git range: {BASE_SHA}..{HEAD_SHA}

  Slice exit criteria:
  {EXIT_CRITERIA_LIST}

  Focus ONLY on:
  - 이 작업이 북극성 문제(Slice exit criteria)를 실제로 줄였는가
  - 로컬 최적화인가 구조 개선인가
  - Slice exit criteria를 얼마나 닫았는가 (구체적으로)
  - 지금 고쳐야 할 것 vs 나중에 미뤄도 될 것 구분

  Output: Exit criteria 진행표 + Findings + 판단
```

#### Agent 4: Product/Business (제품/사업 관점)

```
name: review-product
subagent_type: superpowers:code-reviewer
prompt: |
  You are Lens 4: PRODUCT/BUSINESS REVIEW for {WHAT_WAS_IMPLEMENTED}.
  Git range: {BASE_SHA}..{HEAD_SHA}

  Focus ONLY on:
  - 사용자 기대와 실제 동작이 일치하는가 (모순 UI 여부)
  - 기능이 사용자에게 보이는가 / 묻히는가
  - 진짜 가치 경로를 강화하는가 (곧 버릴 경로에 과투자하지 않는가)
  - 운영 / 확장 / 차별화에 유리한가

  Output: Findings + UX 리스크 + 가치 판단
```

### 3단계: 결과 통합

4개 에이전트의 결과를 **아래 고정 형식**으로 통합하여 사용자에게 보고한다.
내가 severity를 조정하거나 findings를 필터링하지 않는다.

```
## 4-Lens Review 결과

### 1. 핵심 판단
- 진행 가능 / 조건부 진행 / 보류 후 수정

### 2. Findings (4개 렌즈 통합, severity순)
| Severity | Lens | 항목 | file:line |
|----------|------|------|-----------|
| ...      | ...  | ...  | ...       |

### 3. 좋은 점
### 4. 리스크
### 5. 다음 액션 (P0 즉시 / P1 다음 task / P2 이후)
### 6. Slice Exit Criteria 진행표
### 7. 최종 판정
```

### 4단계: P0 수정

**P0 항목이 있으면:**
1. 즉시 수정
2. 수정 후 재검증 (테스트 + 컴파일)
3. 수정 커밋
4. 수정 후에야 다음 Task 진행

**리뷰어가 틀렸다고 판단되면:**
- 기술적 근거를 들어 반박
- 코드/테스트로 증명
- 판단 근거를 명시적으로 기록

## Critical Rules

**DO:**
- 4개 에이전트를 **반드시 하나의 메시지에서 동시에** dispatch
- 각 에이전트에 Slice exit criteria를 전달
- "All clean", "done", "verified" 표현은 증거 있을 때만
- 설계 문서와 구현의 불일치를 반드시 체크
- 사용자 관점의 모순 UI를 반드시 체크

**DON'T:**
- 4개 렌즈를 1개 에이전트에 몰아넣지 마라
- 결과를 요약하거나 severity를 조정하지 마라
- Task 완료를 Slice 진전과 혼동하지 마라
