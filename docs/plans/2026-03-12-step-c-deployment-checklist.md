# Step C: 배포 체크리스트

> 작성: 2026-03-12 | 대상 커밋: `d835e94` | 상태: **준비 중 (배포 실행 전)**

---

## 0. 현재 상태 (사실 기반)

| 항목 | 결과 |
|------|------|
| root pytest | 202 passed, 1 skipped, **1 warning** (joblib/loky, 환경 의존) |
| rag_engine pytest | 367 passed, 0 warnings |
| TypeScript | pass |
| Vite build | pass, index 527KB |
| git status | clean (chroma.sqlite3 binary diff만 존재) |

**"0 warnings"가 아닙니다. joblib/loky 1건이 남아 있습니다.**
- 분류: 환경 의존 (macOS physical core 감지)
- 사용자 영향: 없음
- 배포 blocker: 아님

---

## 1. 배포 전 — 실행 항목

### 1-A. 배포 대상 커밋 고정

```bash
git log --oneline -3
# d835e94 fix: root-cause resolve 9/12 pytest warnings, filter only SWIG (upstream)
# a6b2f1f chore: release hardening — pytest warnings, Vite code-splitting, SQLite leak
# 0571c3d feat: company-specific data isolation for all generation paths
```

### 1-B. git tag 생성

```bash
# 첫 릴리즈 태그 (기존 태그 없음)
git tag -a v1.0.0-rc1 -m "Release candidate 1: company isolation + document pack + hardening"
```

- 롤백 기준: 이 태그 직전 커밋 또는 이전 안정 커밋
- 태그는 배포 승인 후 push: `git push origin v1.0.0-rc1`

### 1-C. Railway 환경변수 점검

**두 서비스 모두 확인 필요:**

| 변수 | 필수 | 누락 시 증상 |
|------|------|-------------|
| `OPENAI_API_KEY` | **필수** | 서버 기동은 됨, 모든 생성 API 503 (health check는 통과) |
| `PORT` | Railway 자동 주입 | — |
| `FASTAPI_URL` | 모놀리스면 기본값 OK (`http://localhost:8001`) | 별도 배포면 반드시 설정 |
| `DATA_GO_KR_API_KEY` | 공고 검색용 | 검색 실패 |
| `VITE_API_BASE_URL` | 빌드 타임 | 프론트→백엔드 연결 실패 |

**운영 리스크: OPENAI_API_KEY 무증상 장애**
- health check(`/api/health`, `/health`)는 키 없이도 200 반환
- 키 만료/삭제 시 서비스 정상 표시 + 모든 AI 기능 503
- 현재 상태: request-time validation (mitigation)
- 근본 해결: boot-time fail-fast (미구현, 배포 blocker는 아님)

### 1-D. railway.toml + Dockerfile 재확인

**Root (모놀리스 — web_app + rag_engine 동시 기동):**
```
railway.toml:
  healthcheckPath = "/api/health"    ← web_app 엔드포인트
  healthcheckTimeout = 100           ← start.sh 기동 시간 포함
  restartPolicyType = "ON_FAILURE"
  restartPolicyMaxRetries = 3

Dockerfile:
  Python 3.11-slim + Node 20 (frontend build)
  Non-root user (app:app)
  CMD: start.sh → rag_engine(8001) → web_app($PORT)
```

**rag_engine (별도 서비스):**
```
railway.toml:
  healthcheckPath = "/health"        ← rag_engine 엔드포인트
  healthcheckTimeout = 30
  restartPolicyType = "ON_FAILURE"
  restartPolicyMaxRetries = 3

Dockerfile:
  Python 3.12-slim
  Non-root user (app:app)
  CMD: uvicorn main:app --host 0.0.0.0 --port 8001
```

**확인 결과:** Health endpoint ↔ railway.toml 경로 일치. restart policy 적절.

---

## 2. 배포 순서

모놀리스 배포 (start.sh가 순서 보장):
1. rag_engine 기동 (port 8001)
2. `/healthz` 폴링 (최대 20초)
3. ChromaDB warmup (`/warmup`)
4. web_app 기동 ($PORT)
5. Railway가 `/api/health` 체크 → 트래픽 라우팅

별도 배포 시:
1. rag_engine 먼저
2. health 확인 후 web_app
3. 프론트엔드는 web_app이 서빙 (Dockerfile stage 1에서 빌드)

---

## 3. 배포 직후 Smoke Test

**자동화 가능 (curl):**

```bash
BASE_URL="https://<railway-app>.up.railway.app"

# 1. Health check
curl -sf "$BASE_URL/api/health" | jq .
# 기대: {"status": "ok"}

# 2. rag_engine health (모놀리스 내부 → 직접 접근 불가, /api/debug/env로 확인)
curl -sf "$BASE_URL/api/debug/env" | jq '.rag_engine_health'
# 기대: "ok"

# 3. OPENAI_API_KEY 설정 여부
curl -sf "$BASE_URL/api/debug/env" | jq '.openai_key_set'
# 기대: true

# 4. 프론트엔드 로드
curl -sf "$BASE_URL/" | head -1
# 기대: <!DOCTYPE html> 또는 HTML 응답

# 5. 세션 생성
curl -sf -X POST "$BASE_URL/api/session" | jq .session_id
# 기대: 세션 ID 문자열
```

**수동 확인 (브라우저):**

| # | 시나리오 | 기대 결과 | 실패 시 조치 |
|---|---------|----------|-------------|
| 1 | 첫 화면 로드 | 랜딩페이지 또는 채팅 UI 표시 | 즉시 롤백 |
| 2 | 세션 생성 | 대화 시작 가능 | 즉시 롤백 |
| 3 | 공고 검색 (키워드 "소프트웨어") | 검색 결과 카드 표시 | DATA_GO_KR_API_KEY 확인 |
| 4 | 문서 분석 (아무 PDF 업로드) | 분석 결과 표시 | OPENAI_API_KEY 확인 |
| 5 | 설정 > 문서관리 진입 | 프로필/제안서 탭 표시 | 프론트 라우팅 확인 |
| 6 | 회사 DB 온보딩 모달 | 실적/인력 입력 화면 | company_id 경로 확인 |

---

## 4. 즉시 롤백 조건

다음 중 하나라도 발생 시 **즉시 롤백**:

- [ ] `/api/health` 200이 아님
- [ ] 프론트엔드 white screen
- [ ] 세션 생성 실패
- [ ] 생성 API 연속 5xx (3회 이상)
- [ ] 인증/쿠키 동작 이상
- [ ] company_id 데이터 경계 이상 (다른 회사 데이터 노출)

### 롤백 절차

```bash
# Railway CLI 롤백 (최근 성공 배포로)
railway service rollback

# 또는 git 기반
git revert d835e94 a6b2f1f 0571c3d  # hardening + isolation 커밋 되돌리기
git push origin main

# 또는 이전 태그로 배포
git checkout v0.x.x  # (이전 안정 태그가 없으므로 첫 배포 시 해당 없음)
```

**첫 배포이므로 롤백 = 서비스 중단.** Railway에서 서비스 비활성화가 유일한 롤백.

---

## 5. 배포 후 모니터링 (15~30분)

| 확인 항목 | 방법 | 주기 |
|----------|------|------|
| 5xx 에러 | Railway logs | 5분 |
| 응답 시간 | Railway metrics | 5분 |
| 생성 API latency | 수동 1건 실행 | 10분 |
| company_id 로그 | Railway logs에서 `company_id` grep | 배포 직후 1회 |
| 메모리 사용량 | Railway metrics | 15분 |

---

## 6. 오너십 관점 한 줄

**이번 배포의 핵심은 "새 기능 공개"가 아니라 회사별 맞춤화와 멀티테넌시가 운영 환경에서도 깨지지 않는지 확인하는 것.**

---

## 강제 체크리스트

```
[사용자 영향] 배포 성공 시: 회사별 격리된 제안서 생성, Document Pack 적용.
              배포 실패 시: 서비스 중단 (첫 배포이므로 기존 사용자 없음).
[원인 분석] 해당 없음 (신규 배포)
[해결 분류] 모든 hardening 항목 root fix (9/12) + suppression with justification (3/12)
[책임과 일정] 배포 실행: 대표 승인 후. 모니터링: 배포 직후 30분 집중.
```
