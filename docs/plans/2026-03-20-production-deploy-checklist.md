# Bid Studio Production 배포 체크리스트

## 사전 준비 (Railway Dashboard)

### Step 1: PostgreSQL 서비스 추가
1. Railway dashboard → 프로젝트 → "New Service" → "Database" → "PostgreSQL"
2. 또는 Railway CLI: `railway add --plugin postgresql`
3. 생성 후 connection string 확인 (형식: `postgresql://user:pass@host:port/dbname`)

### Step 2: pgvector 확장 활성화
Railway PostgreSQL에 접속하여 실행:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

접속 방법:
```bash
# Railway CLI
railway connect postgres

# 또는 psql 직접
psql "CONNECTION_STRING_FROM_RAILWAY"
```

### Step 3: 환경변수 설정 (Railway Dashboard → Variables)

**필수 추가:**
| 변수 | 값 | 비고 |
|------|-----|------|
| `BID_DATABASE_URL` | `postgresql+asyncpg://...` (Railway PG 연결) | asyncpg 프로토콜 필수 |
| `VITE_STUDIO_VISIBLE` | `true` | 빌드 타임 변수 |
| `VITE_CHAT_GENERATION_CUTOVER` | `false` | Phase 1: Studio만 노출 |

**주의:**
- `BID_DATABASE_URL`은 Railway가 제공하는 `DATABASE_URL`과 다름
  - Railway: `postgresql://user:pass@host:port/db`
  - 필요: `postgresql+asyncpg://user:pass@host:port/db`
  - `postgresql://` → `postgresql+asyncpg://` 로 변환 필요
- `VITE_*` 변수는 빌드 타임에 주입되므로 설정 후 재배포 필요
- **`BID_DEV_BOOTSTRAP`는 production에서 설정 금지** — 설정 시 아무 사용자나 org 생성 가능. 초기 org 생성은 DB 직접 INSERT로 수행할 것.

### Step 4: 코드 머지
```bash
# main 브랜치로 이동
git checkout main

# feature 브랜치 머지
git merge feature/html-ppt-poc

# Railway로 배포 (GitHub 연결 시 자동, 아니면)
railway up
# 또는
git push origin main
```

### Step 5: DB 테이블 생성
서버 시작 시 `lifespan` 함수에서 `init_db()` 호출 → `Base.metadata.create_all()` 실행.
별도 Alembic migration은 production 첫 배포 시 불필요 (create_all이 전체 스키마 생성).

이후 스키마 변경 시에만 Alembic migration 사용.

---

## 배포 후 검증

### Step 6: 서버 상태 확인
```bash
# 헬스체크
curl https://YOUR-DOMAIN.up.railway.app/api/health

# Studio 라우터 로드 확인
curl https://YOUR-DOMAIN.up.railway.app/openapi.json | python -c "
import sys,json
d=json.load(sys.stdin)
paths=[p for p in d.get('paths',{}) if 'studio' in p]
print(f'Studio routes: {len(paths)}')
"
```

기대값: Studio routes: 25+

### Step 7: Phase 1 Canary (Studio 노출만)
Internal Canary Checklist (`docs/plans/2026-03-19-internal-canary-checklist.md`) 섹션 1~8 수행.

### Step 8: Phase 2 (Chat Handoff — 선택)
1. Railway Variables에서 `VITE_CHAT_GENERATION_CUTOVER=true` 설정
2. 재배포 (프론트 리빌드 필요)
3. Canary Checklist 섹션 9 수행

---

## Rollback

### 즉시 롤백 (Studio만 비활성화)
Railway Variables에서:
- `VITE_STUDIO_VISIBLE=false`
- `VITE_CHAT_GENERATION_CUTOVER=false`
- 재배포

### 완전 롤백 (Studio DB 연결 해제)
- `BID_DATABASE_URL` 삭제
- 재배포 → Studio 라우터 자체가 등록 안 됨
- Chat 기능은 영향 없음

---

## 모니터링
배포 후 Staged Rollout Runbook (`docs/plans/2026-03-19-staged-rollout-runbook.md`) 참조.
```

