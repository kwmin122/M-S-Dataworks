# Kira Bot

공공조달 입찰 전 과정 자동화 AI 플랫폼. 공고 발견 → RFP 분석 → GO/NO-GO → 제안서 자동 생성 → 체크리스트 → 수정 학습.

## CRITICAL
- 기존 `/api/proposal/generate` 엔드포인트 유지 — 챗봇 초안 기능의 핵심
- Chat=탐색 허브, Studio=정식 생산 경로 — 이 경계를 유지
- 배포 수준 코딩 — 에러 핸들링, 입력 검증, 보안 필수 (MVP 아님)

## 실행 명령어

```bash
# 백엔드 (FastAPI, port 8000)
python services/web_app/main.py

# 프론트엔드 (Vite, port 5173)
cd frontend/kirabot && npm run dev

# RAG Engine (port 8001)
cd rag_engine && uvicorn main:app --reload --port 8001

# 테스트
pytest -q                                    # 레거시
cd rag_engine && pytest -q                   # RAG
cd web_saas && npx jest --no-coverage        # SaaS
cd frontend/kirabot && npx vitest run        # Studio FE

# Studio 테스트 (PostgreSQL 필요)
BID_TEST_DATABASE_URL='postgresql+asyncpg://kira:kira@localhost:5434/kira_bid_test' \
  python -m pytest services/web_app/tests -q
```

## 환경 변수

| 변수 | 용도 |
|------|------|
| `OPENAI_API_KEY` | LLM (분석/생성/채팅) |
| `BID_DATABASE_URL` | Studio PostgreSQL (없으면 Studio 비활성) |
| `DATA_GO_KR_API_KEY` | 나라장터 API |
| `VITE_STUDIO_VISIBLE` | Studio UI 노출 (빌드 타임) |
| `VITE_CHAT_GENERATION_CUTOVER` | Chat→Studio 전환 (빌드 타임) |

전체 환경변수: `~/Desktop/MS_SOLUTIONS/.env`

## 현재 상태 (2026-03-20)

- **Bid Studio Slice 1-5 완료** — Production 배포 (Railway)
- **Ops Hardening 완료** — rate limit, upload allowlist, path traversal guard
- 설계: `docs/plans/2026-03-18-bid-studio-master-design.md`
- 구현 계획: `docs/plans/2026-03-18-bid-studio-master-implementation-plan.md`
- Rollout: `docs/plans/2026-03-19-staged-rollout-runbook.md`

## 아키텍처 요약

```
frontend/kirabot/     React 19 + Vite + TypeScript (Chat UI + Studio)
services/web_app/     FastAPI (메인 서버, port 8000)
  api/studio.py       Studio API (25+ endpoints)
  api/deps.py         인증 + ACL (require_project_access)
rag_engine/           FastAPI (RAG/생성 엔진, port 8001)
web_saas/             Next.js 16 + Prisma (SaaS 스택)
```

## 팀 에이전트

- 작업 전 필독: `docs/agent-memory/context.md`
- 의사결정: `docs/agent-memory/decision-log.md`
- 패턴: `docs/agent-memory/patterns.md`

## CRITICAL (재확인)
- 기존 `/api/proposal/generate` 유지
- Studio staging → shared promote 전에는 shared DB 오염 없음
- 배포 수준 코딩 필수
