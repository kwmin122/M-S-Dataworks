---
name: claudemd-optimizer
description: >
  CLAUDE.md 최적화 스킬. CLAUDE.md에 규칙을 추가/수정/리팩토링할 때, 또는 CLAUDE.md가 비대해졌을 때 자동으로 적용.
  라우팅 패턴 분리(.claude/rules/), 긍정형 규칙 전환, 강도 계층화, primacy/recency 배치를 수행.
  "CLAUDE.md 정리해줘", "규칙 추가해줘", "CLAUDE.md 최적화", "rules 분리", "프로젝트 설정 업데이트"
  같은 요청에 반드시 사용. CLAUDE.md 파일을 수정하는 모든 상황에서 이 스킬을 참조할 것.
---

# CLAUDE.md Optimizer

CLAUDE.md를 프로덕션 수준으로 최적화하는 스킬.
큰 CLAUDE.md를 모듈화하고, 규칙을 효과적으로 작성하며, 토큰을 절약한다.

## 왜 이게 중요한가

CLAUDE.md는 **매 세션마다 전체가 컨텍스트에 로드**된다. 200줄 넘어가면 토큰 낭비 + 규칙 준수율 하락.
반면 `.claude/rules/`의 `paths` 스코프 파일은 **해당 파일을 열 때만** 로드되어 토큰을 아낀다.
부정형("~금지") 규칙은 긍정형("~사용")보다 위반률이 약 2배 높다.
Claude는 primacy/recency bias가 있어 파일 처음/끝에 배치된 규칙을 더 잘 따른다.

## 워크플로우

### Phase 1: 분석

1. 현재 CLAUDE.md를 읽는다
2. `.claude/rules/` 디렉토리가 있으면 기존 rule 파일도 읽는다
3. 아래 기준으로 현황을 평가한다:

| 지표 | 임계값 | 액션 |
|------|--------|------|
| CLAUDE.md 줄 수 | > 200줄 | 라우팅 분리 필요 |
| 부정형 규칙 비율 | > 20% | 긍정형 전환 필요 |
| 강도 계층 없음 | 미분류 | 계층화 필요 |
| CRITICAL 규칙이 중간에 묻힘 | 위치 불량 | 상단/하단 재배치 |

4. 분석 결과를 사용자에게 간결하게 보고한다:
   ```
   CLAUDE.md 분석 결과:
   - 484줄 (권장: 200줄 미만) → 라우팅 분리 필요
   - 부정형 규칙 12개 발견 → 긍정형 전환
   - 강도 계층 미적용 → CRITICAL/MANDATORY/PREFER 분류
   - 진행할까요?
   ```

### Phase 2: 설계

사용자 확인 후, 분리 계획을 세운다.

**도메인 분류 기준** — CLAUDE.md의 `##` 섹션을 아래 도메인으로 매핑:

| 도메인 | paths 스코프 | 포함 내용 |
|--------|-------------|-----------|
| `core.md` | (없음 — 항상 로드) | 프로젝트 개요, 실행 명령어, 환경변수 |
| `backend.md` | `services/**`, `*.py` | Python 백엔드 아키텍처, 설계 결정 |
| `frontend.md` | `frontend/**`, `*.tsx`, `*.ts` | 프론트엔드 제약, UI 구조 |
| `saas.md` | `web_saas/**` | SaaS 잡 시스템, Prisma, HMAC |
| `rag-engine.md` | `rag_engine/**` | A-lite 파이프라인, Layer 1/2 |
| `testing.md` | `tests/**`, `**/tests/**`, `**/__tests__/**` | 테스트 파일 매핑, Jest 제약 |
| `security.md` | (없음 — 항상 로드) | 보안 레이어, CSRF, SSRF, IDOR |

각 프로젝트마다 도메인은 다르다. CLAUDE.md의 실제 내용을 보고 적절한 도메인을 설계할 것.
위 표는 예시일 뿐이다.

**분리 판단 기준:**
- 200줄 미만이면 분리하지 않고 규칙 품질 개선만 수행
- 200~400줄이면 2~4개 rule 파일로 분리
- 400줄 이상이면 5개+ rule 파일로 분리
- 단, `.claude/rules/`에 이미 파일이 있으면 기존 구조를 존중하고 병합

### Phase 3: 규칙 품질 개선

분리 여부와 관계없이 **모든 규칙에** 아래 변환을 적용한다:

#### 3-1. 부정형 → 긍정형 전환

부정형 패턴을 찾아 긍정형으로 바꾼다. 의미가 변하지 않도록 주의.

```
Before: process.env.* 직접 접근 금지
After:  환경변수는 getEnv()로 접근

Before: gen_random_uuid() 금지
After:  ID 생성은 createId() (cuid2) 사용

Before: request.json() 직접 호출 금지
After:  request.text() → HMAC 검증 → JSON.parse() 순서로 처리

Before: 직접 state 변경 금지
After:  상태 변경은 dispatch 기반 ChatContext 사용
```

변환 원칙:
- "X 금지/하지마" → "대신 Y 사용/Y로 처리"
- 금지 대상만 있고 대안이 없으면 "~하지 않는다" 형태 유지 (무리하게 바꾸지 않음)
- 맥락상 부정형이 더 명확한 경우 그대로 둠 (예: "절대 삭제 금지" — CRITICAL 규칙)

#### 3-2. 강도 계층 분류

모든 규칙을 3단계로 분류한다:

```markdown
## CRITICAL
가장 중요한 규칙. 위반 시 시스템 장애나 데이터 손실 가능.
- 기존 /api/proposal/generate 엔드포인트 절대 삭제 금지
- 중간 상태 DB 저장 금지 (인메모리만)

## MANDATORY
반드시 따라야 하는 표준 규칙.
- 환경변수는 getEnv()로 접근
- ID 생성은 createId() 사용
- 락 획득은 UPDATE WHERE locked_at IS NULL + affected rows 검사

## PREFER
가능하면 따르되, 상황에 따라 유연하게.
- 기존 Tailwind 클래스 재사용
- call_with_retry() 패턴 활용
```

분류 기준:
- **CRITICAL**: 위반 시 기능 파괴, 데이터 손실, 보안 취약점
- **MANDATORY**: 코드 품질, 일관성, 팀 표준
- **PREFER**: 스타일, 편의성, 최적화

#### 3-3. Primacy/Recency 배치

각 파일(CLAUDE.md 또는 rule 파일)에서:
- **처음 10줄 이내**: 가장 자주 어기는 규칙 또는 CRITICAL 규칙
- **마지막 10줄 이내**: 두 번째로 중요한 규칙 반복 또는 요약

### Phase 4: 작성

#### CLAUDE.md (허브)

분리 후 CLAUDE.md는 다음만 포함:

```markdown
# [프로젝트 이름]

[1~2줄 프로젝트 설명]

## CRITICAL
[CRITICAL 규칙 — 2~5개만]

## 실행 명령어
[빌드/테스트/실행 커맨드]

## 환경변수
[필수 환경변수 테이블]

## 현재 진행 중
[활성 작업 요약 — 5줄 이내]

## CRITICAL (재확인)
[상단 CRITICAL 규칙 다시 한번 — primacy/recency]
```

목표: **100줄 이내**. 절대 200줄을 넘기지 않는다.

#### .claude/rules/ 파일

각 rule 파일 형식:

```markdown
---
paths:
  - "frontend/**"
  - "*.tsx"
---

## CRITICAL
- [이 도메인의 CRITICAL 규칙]

## MANDATORY
- [표준 규칙들]

## PREFER
- [권장 사항들]

## 아키텍처
[도메인별 아키텍처 설명]

## CRITICAL (재확인)
- [상단 CRITICAL 반복]
```

#### 작성 원칙

1. **기존 내용을 삭제하지 않는다** — 분류하고 옮길 뿐
2. **의미를 변경하지 않는다** — 긍정형 전환 시 원래 의도 보존
3. **사용자에게 diff를 보여준다** — 변경 전/후 주요 차이점을 간결하게 설명
4. **테스트 매핑 같은 참조 테이블**은 testing.md로 통째로 이동
5. **기능 구현 현황**은 별도 rule 파일 대신 docs/에 이동하거나 CLAUDE.md에 축약

### Phase 5: 검증

작성 완료 후:

1. CLAUDE.md가 200줄 미만인지 확인
2. 각 rule 파일의 `paths` 패턴이 실제 프로젝트 디렉토리와 일치하는지 확인
3. 원본 CLAUDE.md의 모든 규칙이 새 구조 어딘가에 존재하는지 확인
4. 부정형 규칙 잔존 여부 확인
5. CRITICAL 규칙이 각 파일 상단/하단에 배치되었는지 확인

누락된 규칙이 있으면 적절한 파일에 추가한다.

## 규칙 추가 모드

사용자가 CLAUDE.md에 새 규칙을 추가하려 할 때:

1. `.claude/rules/`가 이미 분리되어 있으면 → 적절한 rule 파일에 추가
2. 분리 안 되어 있고 CLAUDE.md < 200줄이면 → CLAUDE.md에 직접 추가
3. 분리 안 되어 있고 CLAUDE.md >= 200줄이면 → 분리를 먼저 제안

새 규칙 추가 시에도:
- 긍정형 프레이밍 적용
- 강도 계층 태깅
- 적절한 위치 배치

## 주의사항

- **@ import 문법은 CLAUDE.md에서 다른 파일을 참조할 때 사용 가능**하지만, `.claude/rules/`의 자동 로딩이 더 효율적이다. 상황에 따라 선택.
- **paths가 없는 rule 파일은 항상 로드된다** — 보안/핵심 규칙처럼 모든 상황에 필요한 규칙에 사용.
- **기존 .claude/rules/ 파일이 있으면 덮어쓰지 않는다** — 병합하거나 사용자에게 확인.
- 이 스킬은 어떤 프로젝트의 CLAUDE.md에든 적용 가능하다. 프로젝트 구조를 먼저 파악하고 도메인을 결정할 것.
