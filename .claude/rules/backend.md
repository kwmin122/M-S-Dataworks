---
paths:
  - "services/**"
  - "*.py"
  - "rag_engine/**"
---

## CRITICAL
- 기존 `/api/proposal/generate` 엔드포인트 유지 — 챗봇 초안 기능의 핵심. v2는 별개 엔드포인트
- 중간 상태(FETCHING/PARSING/EVALUATING)는 인메모리만 — DB 저장 시 크래시 복구 불가

## MANDATORY

### SaaS 잡 시스템
- 락 획득: `UPDATE WHERE locked_at IS NULL` + affected rows 검사
- ID 생성: `createId()` (cuid2, 앱 레벨) 사용
- 시간: `PGTZ=UTC`, `Date.UTC()` 사용

### HMAC 웹훅 / 내부 API
- 서명 문자열: `${ts}.${nonce}.${rawBody}` — nonce 필수
- 요청 처리: `request.text()` → HMAC 검증 → `JSON.parse()` 순서
- Nonce 중복: `UsedNonce.create()` create-only + P2002 catch
- 내부 API도 동일 패턴: `verifyInternalAuth(req, rawBody)`

### 보안 레이어
- 환경변수: `getEnv()` zod 검증으로 접근 (SaaS)
- SSRF: `safeFetch(url, allowedDomains)` — https only, DNS 사전 해석, private IP 차단
- CSRF: `verifyCsrfOrigin(req)` — POST/PUT/PATCH/DELETE에 Origin allowlist 검증
- IDOR: `organizationId`는 세션에서 주입 (`getServerSession()` → `session.user.organizationId`)

### 쿼터 관리
- `consumeQuotaIfNeeded()`: `$transaction` 내 원자 실행
- `quotaConsumed=true`로 재시도 중복 차감 방지

### RAG 파이프라인
- BM25 + 벡터 RRF 하이브리드 (`RAG_HYBRID_ENABLED=1`), BM25 rebuild `threading.Lock` 보호
- 병렬화: `ThreadPoolExecutor`로 청크(max 4), 요건 매칭(max 6) 병렬
- 비동기: `asyncio.to_thread()`로 이벤트 루프 차단 방지
- LLM: `call_with_retry()` — timeout 60초 + 재시도 2회

### A-lite 파이프라인
- mistune 3.x AST 기반 마크다운→DOCX 변환
- Pydantic 입력 검증: `RfxResultInput` 스키마
- 파일명: `re.sub(r'[^a-zA-Z0-9가-힣._-]', '_', ...)` 화이트리스트 + 100자
- auto_learner: `threading.Lock`으로 전역 dict 보호
- 배포 수준 코딩 — 에러 핸들링, 입력 검증, 스레드 안전성 필수

### Prisma 마이그레이션 (오프라인)
- DATABASE_URL 없이 스키마 변경 시: `web_saas/prisma/migrations/YYYYMMDDHHMMSS_<name>/migration.sql` 수동 생성
- `npx prisma generate`는 DATABASE_URL 없이도 가능

### 나라장터 API
- 첨부파일 API: `inqryDiv=2` (공고번호 기준) 필수
- 모든 공고에 e발주 첨부파일이 있진 않음 — 없으면 수동 업로드 폴백

## PREFER
- 기존 패턴(`call_with_retry` 등) 있으면 재활용
- 동의어 사전(`rfp_synonyms.py`) 17개 카테고리 프롬프트 주입 활용
