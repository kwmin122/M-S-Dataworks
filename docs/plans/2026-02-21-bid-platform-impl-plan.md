# B2B SaaS 입찰공고 플랫폼 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 나라장터 공고를 자동 수집·분석하고 입찰 가능 여부를 멀티테넌트로 알려주는 B2B SaaS 플랫폼 구축.

**Architecture:** Next.js(웹+API) + FastAPI(RAG 엔진) + n8n(크롤러+워커) + PostgreSQL(Prisma). Docker Compose로 전 서비스 통합. n8n이 HMAC-signed webhook으로 Next.js를 호출하고, Next.js가 FastAPI에 평가를 위임한다.

**Tech Stack:** Next.js 15 (App Router), Prisma 6, PostgreSQL 16, FastAPI 0.115, n8n (self-hosted), Resend, Stripe, cuid2, Docker Compose

**설계 문서:** `docs/plans/2026-02-20-bid-platform-design.md`

---

## Phase 1 — DB 스키마 & 인프라

### Task 1: Docker Compose 기반 환경 구성

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

**Step 1: `docker-compose.yml` 작성**

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      PGTZ: UTC
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  web:
    build: ./web_saas
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: ${DATABASE_URL}
      WEBHOOK_SECRET: ${WEBHOOK_SECRET}
      FASTAPI_URL: http://rag_engine:8001
      RESEND_API_KEY: ${RESEND_API_KEY}
      STRIPE_SECRET_KEY: ${STRIPE_SECRET_KEY}
      STRIPE_WEBHOOK_SECRET: ${STRIPE_WEBHOOK_SECRET}
    depends_on:
      - postgres

  rag_engine:
    build: ./rag_engine
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: ${DATABASE_URL}

  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      N8N_WEBHOOK_URL: http://web:3000
      WEBHOOK_SECRET: ${WEBHOOK_SECRET}
      DATABASE_URL: ${DATABASE_URL}
      G2B_API_KEY: ${G2B_API_KEY}
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - postgres

volumes:
  postgres_data:
  n8n_data:
```

**Step 2: `.env.example` 작성**

```bash
# .env.example
POSTGRES_USER=bid_user
POSTGRES_PASSWORD=changeme
POSTGRES_DB=bid_platform
DATABASE_URL="postgresql://bid_user:changeme@localhost:5432/bid_platform?timezone=UTC"

WEBHOOK_SECRET=change_this_to_a_random_32_char_string
G2B_API_KEY=your_g2b_openapi_key

RESEND_API_KEY=re_xxxx
STRIPE_SECRET_KEY=sk_test_xxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxx
```

**Step 3: 커밋**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: add docker-compose and env template"
```

---

### Task 2: Prisma 스키마 교체

**Files:**
- Modify: `web_saas/prisma/schema.prisma`

**Step 1: 기존 스키마를 설계 문서 §2 전체로 교체**

`web_saas/prisma/schema.prisma` 를 아래 내용으로 **완전 교체**:

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

enum IngestionJobStatus {
  NEW
  FETCH_ERROR
  PARSE_ERROR
  COMPLETED
  RETRY_EXHAUSTED
}

enum EvaluationJobStatus {
  PENDING
  SCORED
  SCORE_ERROR
  QUOTA_EXCEEDED
  NOTIFIED
  NOTIFY_ERROR
  RETRY_EXHAUSTED
}

enum PlanTier {
  FREE
  PRO
}

model Organization {
  id             String          @id @default(cuid())
  name           String
  companyFacts   Json            @map("company_facts")
  interestConfig Json?           @map("interest_config")
  createdAt      DateTime        @default(now()) @map("created_at")
  updatedAt      DateTime        @updatedAt @map("updated_at")
  subscription   Subscription?
  evaluationJobs EvaluationJob[]
  @@map("organizations")
}

model Subscription {
  id                 String    @id @default(cuid())
  organizationId     String    @unique @map("organization_id")
  organization       Organization @relation(fields: [organizationId], references: [id], onDelete: Cascade)
  plan               PlanTier  @default(FREE)
  status             String
  stripeSubId        String?   @map("stripe_sub_id")
  currentPeriodStart DateTime  @map("current_period_start")
  currentPeriodEnd   DateTime  @map("current_period_end")
  createdAt          DateTime  @default(now()) @map("created_at")
  updatedAt          DateTime  @updatedAt @map("updated_at")
  @@map("subscriptions")
}

model UsageQuota {
  id             String    @id @default(cuid())
  organizationId String    @map("organization_id")
  periodStart    DateTime  @map("period_start")
  usedCount      Int       @default(0) @map("used_count")
  maxCount       Int       @map("max_count")
  createdAt      DateTime  @default(now()) @map("created_at")
  updatedAt      DateTime  @updatedAt @map("updated_at")
  @@unique([organizationId, periodStart])
  @@map("usage_quotas")
}

model BidNotice {
  id             String    @id @default(cuid())
  source         String
  externalId     String    @map("external_id")
  title          String
  category       String?
  region         String?
  url            String?
  publishedAt    DateTime? @map("published_at")
  deadlineAt     DateTime? @map("deadline_at")
  attachmentText String?   @map("attachment_text") @db.Text
  createdAt      DateTime  @default(now()) @map("created_at")
  ingestionJobs  IngestionJob[]
  evaluationJobs EvaluationJob[]
  @@unique([source, externalId])
  @@map("bid_notices")
}

model IngestionJob {
  id              String             @id @default(cuid())
  bidNoticeId     String             @map("bid_notice_id")
  bidNotice       BidNotice          @relation(fields: [bidNoticeId], references: [id], onDelete: Cascade)
  status          IngestionJobStatus @default(NEW)
  idempotencyKey  String             @unique @map("idempotency_key")
  provisionalHash String             @map("provisional_hash")
  contentHash     String?            @map("content_hash")
  attachmentUrl   String?            @map("attachment_url")
  retryCount      Int                @default(0) @map("retry_count")
  lockedAt        DateTime?          @map("locked_at")
  lockOwner       String?            @map("lock_owner")
  nextRetryAt     DateTime?          @map("next_retry_at")
  createdAt       DateTime           @default(now()) @map("created_at")
  updatedAt       DateTime           @updatedAt @map("updated_at")
  @@index([status, lockedAt, nextRetryAt])
  @@map("ingestion_jobs")
}

model EvaluationJob {
  id               String              @id @default(cuid())
  organizationId   String              @map("organization_id")
  organization     Organization        @relation(fields: [organizationId], references: [id], onDelete: Cascade)
  bidNoticeId      String              @map("bid_notice_id")
  bidNotice        BidNotice           @relation(fields: [bidNoticeId], references: [id], onDelete: Cascade)
  status           EvaluationJobStatus @default(PENDING)
  idempotencyKey   String              @unique @map("idempotency_key")
  noticeRevision   String              @map("notice_revision")
  evaluationReason String              @map("evaluation_reason")
  isEligible       Boolean?            @map("is_eligible")
  details          Json?
  actionPlan       String?             @map("action_plan") @db.Text
  quotaConsumed    Boolean             @default(false) @map("quota_consumed")
  retryCount       Int                 @default(0) @map("retry_count")
  lockedAt         DateTime?           @map("locked_at")
  lockOwner        String?             @map("lock_owner")
  nextRetryAt      DateTime?           @map("next_retry_at")
  createdAt        DateTime            @default(now()) @map("created_at")
  updatedAt        DateTime            @updatedAt @map("updated_at")
  @@index([organizationId, bidNoticeId])
  @@index([status, lockedAt, nextRetryAt])
  @@map("evaluation_jobs")
}

model UsedNonce {
  id        String   @id @default(cuid())
  nonce     String   @unique
  expiredAt DateTime @map("expired_at")
  @@index([expiredAt])
  @@map("used_nonces")
}
```

**Step 2: Next.js 프로젝트 초기화 (web_saas에 package.json 없을 경우)**

```bash
cd web_saas && npx create-next-app@latest . --typescript --tailwind --app --src-dir --import-alias "@/*" --use-npm
```

**Step 3: Prisma 의존성 설치**

```bash
cd web_saas
npm install prisma @prisma/client
npm install @paralleldrive/cuid2
npx prisma generate
```

**Step 4: 마이그레이션 실행** (PostgreSQL이 실행 중이어야 함)

```bash
cd web_saas
npx prisma migrate dev --name init_bid_platform
```

Expected: `✔ Generated Prisma Client` + `migrations/TIMESTAMP_init_bid_platform/migration.sql` 생성.

**Step 5: 커밋**

```bash
git add web_saas/prisma/ web_saas/package.json web_saas/package-lock.json
git commit -m "feat: replace prisma schema with bid platform models"
```

---

### Task 3: Prisma Client 싱글턴 + 공용 유틸리티

**Files:**
- Create: `web_saas/src/lib/prisma.ts`
- Create: `web_saas/src/lib/ids.ts`
- Create: `web_saas/src/lib/errors.ts`

**Step 1: `web_saas/src/lib/prisma.ts`**

```typescript
import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({ log: ['query', 'error', 'warn'] });

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
```

**Step 2: `web_saas/src/lib/ids.ts`**

```typescript
import { createId } from '@paralleldrive/cuid2';
export { createId };
```

**Step 3: `web_saas/src/lib/errors.ts`**

```typescript
import { Prisma } from '@prisma/client';

export function isUniqueConstraintError(e: unknown): boolean {
  return (
    e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2002'
  );
}
```

**Step 4: 커밋**

```bash
git add web_saas/src/lib/
git commit -m "feat: add prisma singleton, ids, error utils"
```

---

## Phase 2 — FastAPI RAG 엔진

### Task 4: FastAPI 프로젝트 초기화

**Files:**
- Create: `rag_engine/requirements.txt`
- Create: `rag_engine/Dockerfile`
- Create: `rag_engine/main.py`
- Create: `rag_engine/models.py`

**Step 1: `rag_engine/requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.32.1
pydantic==2.10.4
httpx==0.28.1
python-multipart==0.0.20
```

기존 Python 의존성이 있다면 `rfx_analyzer.py`, `matcher.py`, `engine.py`에서 import 목록 확인 후 추가.

**Step 2: `rag_engine/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 기존 RAG 로직 파일 복사
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Step 3: `rag_engine/models.py`**

```python
from pydantic import BaseModel
from typing import Any

class AnalyzeBidRequest(BaseModel):
    organization_id: str
    bid_notice_id: str
    company_facts: dict[str, Any]
    attachment_text: str

class EvaluationDetails(BaseModel):
    missingLicenses: list[str] = []
    insufficientCapital: bool = False
    regionMismatch: bool = False
    confidenceScore: float = 1.0

class AnalyzeBidResponse(BaseModel):
    is_eligible: bool
    details: dict[str, Any]   # NoticeScore.details JSON contract
    action_plan: str
```

**Step 4: `rag_engine/main.py`**

```python
import sys
import os

# 루트 디렉터리의 기존 RAG 파일 참조 (Docker에서는 COPY로 같은 위치에 있음)
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from models import AnalyzeBidRequest, AnalyzeBidResponse

# 기존 로직 import — rfx_analyzer.py, matcher.py, engine.py가 rag_engine/에 복사되어야 함
try:
    from engine import BidEngine  # 실제 클래스명으로 교체
except ImportError:
    BidEngine = None  # 로컬 개발 시 모킹 허용

app = FastAPI(title="Bid RAG Engine", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/analyze-bid", response_model=AnalyzeBidResponse)
def analyze_bid(req: AnalyzeBidRequest) -> AnalyzeBidResponse:
    if BidEngine is None:
        raise HTTPException(status_code=503, detail="Engine not loaded")

    engine = BidEngine()
    result = engine.analyze(
        company_facts=req.company_facts,
        attachment_text=req.attachment_text,
    )

    return AnalyzeBidResponse(
        is_eligible=result.is_eligible,
        details={
            "_meta": {
                "schemaVersion": "1.0",
                "engineVersion": "v1.0.0",
                "evaluatedAt": result.evaluated_at,
            },
            "evaluation": {
                "missingLicenses": result.missing_licenses,
                "insufficientCapital": result.insufficient_capital,
                "regionMismatch": result.region_mismatch,
                "confidenceScore": result.confidence_score,
            },
            "rawOutput": {"matchedChunks": result.matched_chunks},
        },
        action_plan=result.action_plan,
    )
```

> **주의**: `engine.py`의 실제 클래스/함수 시그니처를 확인하고 `analyze()` 호출부를 맞게 수정.
> `engine.py`, `matcher.py`, `rfx_analyzer.py`를 `rag_engine/` 폴더로 복사하거나 심볼릭 링크 설정 필요.

**Step 5: 기존 RAG 파일을 rag_engine으로 복사**

```bash
cp rfx_analyzer.py rag_engine/
cp matcher.py rag_engine/
cp engine.py rag_engine/
cp response_parser.py rag_engine/
```

**Step 6: 로컬에서 FastAPI 기동 테스트**

```bash
cd rag_engine
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
# http://localhost:8001/health → {"status":"ok"} 확인
```

**Step 7: 커밋**

```bash
git add rag_engine/
git commit -m "feat: initialize fastapi rag engine microservice"
```

---

### Task 5: FastAPI `/api/analyze-bid` 통합 테스트

**Files:**
- Create: `rag_engine/tests/test_analyze_bid.py`

**Step 1: 테스트 파일 작성**

```python
# rag_engine/tests/test_analyze_bid.py
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from main import app

client = TestClient(app)

SAMPLE_FACTS = {
    "_meta": {"schemaVersion": "1.0", "updatedAt": "2026-01-01T00:00:00Z", "source": "manual_input"},
    "facts": {
        "region": "경기도",
        "foundationDate": "2015-05-01",
        "capital": 100000000,
        "licenses": [{"code": "0037", "name": "정보통신공사업"}],
        "certifications": [],
        "pastPerformances": [],
    },
}

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_analyze_bid_returns_valid_shape():
    r = client.post("/api/analyze-bid", json={
        "organization_id": "org_test",
        "bid_notice_id": "notice_test",
        "company_facts": SAMPLE_FACTS,
        "attachment_text": "정보통신공사업 면허 보유 업체 입찰 가능",
    })
    assert r.status_code == 200
    body = r.json()
    assert "is_eligible" in body
    assert "details" in body
    assert "_meta" in body["details"]
    assert "evaluation" in body["details"]
    assert "action_plan" in body
```

**Step 2: 테스트 실행**

```bash
cd rag_engine
pip install pytest httpx
pytest tests/test_analyze_bid.py -v
```

Expected: 2 tests PASS.

**Step 3: 커밋**

```bash
git add rag_engine/tests/
git commit -m "test: add fastapi analyze-bid integration tests"
```

---

## Phase 3 — Next.js HMAC Webhook

### Task 6: HMAC 유틸리티 구현 + 단위 테스트

**Files:**
- Create: `web_saas/src/lib/hmac.ts`
- Create: `web_saas/src/lib/__tests__/hmac.test.ts`

**Step 1: 테스트 먼저 작성 (TDD)**

```typescript
// web_saas/src/lib/__tests__/hmac.test.ts
import { buildSigningString, verifyWebhookSignature } from '../hmac';
import { createHmac, timingSafeEqual } from 'crypto';

const SECRET = 'test_secret_32_chars_long_xxxxxx';

describe('buildSigningString', () => {
  it('should concatenate timestamp.nonce.body', () => {
    const result = buildSigningString('1700000000', 'my-nonce', '{"foo":1}');
    expect(result).toBe('1700000000.my-nonce.{"foo":1}');
  });
});

describe('verifyWebhookSignature', () => {
  it('should return true for valid signature', () => {
    const ts = '1700000000';
    const nonce = 'test-nonce';
    const body = '{"event":"test"}';
    const signingString = `${ts}.${nonce}.${body}`;
    const expected = createHmac('sha256', SECRET)
      .update(signingString)
      .digest('hex');

    expect(verifyWebhookSignature({ ts, nonce, rawBody: body, signature: expected, secret: SECRET })).toBe(true);
  });

  it('should return false for tampered nonce', () => {
    const ts = '1700000000';
    const body = '{"event":"test"}';
    const signingString = `${ts}.original-nonce.${body}`;
    const sig = createHmac('sha256', SECRET).update(signingString).digest('hex');

    // 다른 nonce로 검증 시도
    expect(verifyWebhookSignature({ ts, nonce: 'tampered-nonce', rawBody: body, signature: sig, secret: SECRET })).toBe(false);
  });
});
```

**Step 2: 테스트가 실패하는지 확인**

```bash
cd web_saas && npm test -- --testPathPattern=hmac
```

Expected: FAIL (hmac.ts 없음)

**Step 3: `web_saas/src/lib/hmac.ts` 구현**

```typescript
import { createHmac, timingSafeEqual } from 'crypto';

export function buildSigningString(ts: string, nonce: string, rawBody: string): string {
  return `${ts}.${nonce}.${rawBody}`;
}

interface VerifyOptions {
  ts: string;
  nonce: string;
  rawBody: string;
  signature: string;
  secret: string;
}

export function verifyWebhookSignature({ ts, nonce, rawBody, signature, secret }: VerifyOptions): boolean {
  const signingString = buildSigningString(ts, nonce, rawBody);
  const expected = createHmac('sha256', secret).update(signingString).digest('hex');
  try {
    return timingSafeEqual(Buffer.from(expected, 'hex'), Buffer.from(signature, 'hex'));
  } catch {
    return false;
  }
}
```

**Step 4: 테스트 재실행**

```bash
cd web_saas && npm test -- --testPathPattern=hmac
```

Expected: 3 tests PASS.

**Step 5: 커밋**

```bash
git add web_saas/src/lib/hmac.ts web_saas/src/lib/__tests__/hmac.test.ts
git commit -m "feat: add hmac webhook signature utility"
```

---

### Task 7: Webhook 수신 엔드포인트

**Files:**
- Create: `web_saas/src/app/api/webhooks/n8n/route.ts`

**Step 1: 파일 작성**

```typescript
// web_saas/src/app/api/webhooks/n8n/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';
import { verifyWebhookSignature } from '@/lib/hmac';
import { isUniqueConstraintError } from '@/lib/errors';

const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET!;
const REPLAY_WINDOW_SEC = 300; // ±5분

export async function POST(req: NextRequest) {
  const rawBody = await req.text();
  const ts        = req.headers.get('x-timestamp') ?? '';
  const nonce     = req.headers.get('x-nonce') ?? '';
  const signature = req.headers.get('x-signature') ?? '';

  // 1. Timestamp 범위
  const tsNum = parseInt(ts, 10);
  if (!tsNum || Math.abs(Date.now() / 1000 - tsNum) > REPLAY_WINDOW_SEC) {
    return NextResponse.json({ error: 'timestamp_out_of_range' }, { status: 401 });
  }

  // 2. 서명 검증 (nonce 포함)
  const valid = verifyWebhookSignature({ ts, nonce, rawBody, signature, secret: WEBHOOK_SECRET });
  if (!valid) {
    return NextResponse.json({ error: 'invalid_signature' }, { status: 401 });
  }

  // 3. Nonce 중복 방지 (create-only + unique constraint)
  try {
    await prisma.usedNonce.create({
      data: { id: createId(), nonce, expiredAt: new Date((tsNum + 10 * 60) * 1000) },
    });
  } catch (e) {
    if (isUniqueConstraintError(e)) {
      return NextResponse.json({ error: 'replay_detected' }, { status: 409 });
    }
    throw e;
  }

  // 4. 이벤트 디스패치
  const payload = JSON.parse(rawBody) as { event: string; data: unknown };
  await dispatchEvent(payload.event, payload.data);

  return NextResponse.json({ ok: true });
}

async function dispatchEvent(event: string, data: unknown) {
  switch (event) {
    case 'ingestion.completed':
      await handleIngestionCompleted(data as IngestionCompletedPayload);
      break;
    case 'evaluation.status':
      await handleEvaluationStatus(data as EvaluationStatusPayload);
      break;
    default:
      console.warn(`[webhook] unknown event: ${event}`);
  }
}

// --- 타입 정의 ---
interface IngestionCompletedPayload {
  ingestionJobId: string;
  bidNoticeId: string;
  contentHash: string;
}

interface EvaluationStatusPayload {
  evaluationJobId: string;
  status: string;
  isEligible?: boolean;
  details?: object;
  actionPlan?: string;
}

// --- 핸들러 (Task 8, 9에서 구현) ---
async function handleIngestionCompleted(_payload: IngestionCompletedPayload) {
  // Task 8에서 구현: createEvaluationJobsForBidNotice 호출
}

async function handleEvaluationStatus(_payload: EvaluationStatusPayload) {
  // Task 9에서 구현: EvaluationJob 상태 업데이트
}
```

**Step 2: 커밋**

```bash
git add web_saas/src/app/api/webhooks/
git commit -m "feat: add n8n webhook receiver with hmac verification"
```

---

### Task 8: `createEvaluationJobsForBidNotice` 구현 + 테스트

**Files:**
- Create: `web_saas/src/lib/jobs/createEvaluationJobs.ts`
- Create: `web_saas/src/lib/jobs/__tests__/createEvaluationJobs.test.ts`

**Step 1: 테스트 먼저 작성**

```typescript
// web_saas/src/lib/jobs/__tests__/createEvaluationJobs.test.ts
import { matchesInterestConfig } from '../createEvaluationJobs';

describe('matchesInterestConfig', () => {
  const notice = { title: 'CCTV 설치 공사', category: '정보통신', region: '경기도' };

  it('returns true when keyword matches title', () => {
    expect(matchesInterestConfig({ keywords: ['CCTV'], regions: [] }, notice)).toBe(true);
  });

  it('returns true when keyword matches category', () => {
    expect(matchesInterestConfig({ keywords: ['정보통신'], regions: [] }, notice)).toBe(true);
  });

  it('returns false when keyword has no match', () => {
    expect(matchesInterestConfig({ keywords: ['소방'], regions: [] }, notice)).toBe(false);
  });

  it('returns false when region mismatches', () => {
    expect(matchesInterestConfig({ keywords: ['CCTV'], regions: ['서울특별시'] }, notice)).toBe(false);
  });

  it('returns true when regions is empty (전국)', () => {
    expect(matchesInterestConfig({ keywords: ['CCTV'], regions: [] }, notice)).toBe(true);
  });

  it('returns false when interestConfig is null', () => {
    expect(matchesInterestConfig(null, notice)).toBe(false);
  });
});
```

**Step 2: 테스트 실패 확인**

```bash
cd web_saas && npm test -- --testPathPattern=createEvaluationJobs
```

**Step 3: 구현**

```typescript
// web_saas/src/lib/jobs/createEvaluationJobs.ts
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

interface InterestConfig {
  keywords: string[];
  regions: string[];
}

interface NoticeMeta {
  title: string;
  category?: string | null;
  region?: string | null;
}

export function matchesInterestConfig(config: InterestConfig | null, notice: NoticeMeta): boolean {
  if (!config?.keywords?.length) return false;

  const keywordMatch = config.keywords.some(
    kw => notice.title.includes(kw) || (notice.category ?? '').includes(kw)
  );
  const regionMatch =
    !config.regions?.length || config.regions.includes(notice.region ?? '');

  return keywordMatch && regionMatch;
}

export async function createEvaluationJobsForBidNotice(params: {
  bidNoticeId: string;
  noticeRevision: string;
  noticeMeta: NoticeMeta;
}) {
  const { bidNoticeId, noticeRevision, noticeMeta } = params;

  const orgs = await prisma.organization.findMany({
    where: { subscription: { status: { in: ['ACTIVE', 'TRIALING'] } } },
    select: { id: true, interestConfig: true },
  });

  for (const org of orgs) {
    const config = org.interestConfig as InterestConfig | null;
    if (!matchesInterestConfig(config, noticeMeta)) continue;

    const idempotencyKey = `${org.id}:${bidNoticeId}:${noticeRevision}:auto`;
    await prisma.evaluationJob.upsert({
      where: { idempotencyKey },
      create: {
        id: createId(),
        organizationId: org.id,
        bidNoticeId,
        idempotencyKey,
        noticeRevision,
        evaluationReason: 'auto',
      },
      update: {},
    });
  }
}
```

**Step 4: 테스트 재실행**

```bash
cd web_saas && npm test -- --testPathPattern=createEvaluationJobs
```

Expected: 6 tests PASS.

**Step 5: Webhook 핸들러에 연결 (`handleIngestionCompleted` 구현)**

`web_saas/src/app/api/webhooks/n8n/route.ts` 의 `handleIngestionCompleted` 를 수정:

```typescript
import { createEvaluationJobsForBidNotice } from '@/lib/jobs/createEvaluationJobs';

async function handleIngestionCompleted(payload: IngestionCompletedPayload) {
  const notice = await prisma.bidNotice.findUnique({
    where: { id: payload.bidNoticeId },
    select: { title: true, category: true, region: true },
  });
  if (!notice) return;

  await createEvaluationJobsForBidNotice({
    bidNoticeId: payload.bidNoticeId,
    noticeRevision: payload.contentHash,
    noticeMeta: notice,
  });
}
```

**Step 6: 커밋**

```bash
git add web_saas/src/lib/jobs/
git commit -m "feat: add createEvaluationJobs with interestConfig matching"
```

---

### Task 9: `consumeQuotaIfNeeded` 구현 + 테스트

**Files:**
- Create: `web_saas/src/lib/quota/consumeQuota.ts`
- Create: `web_saas/src/lib/quota/__tests__/consumeQuota.test.ts`

**Step 1: 테스트 작성 (mock 사용)**

```typescript
// web_saas/src/lib/quota/__tests__/consumeQuota.test.ts
// Prisma 트랜잭션을 모킹하는 단위 테스트
import { getMaxCountForPlan, FREE_PLAN_LIMIT } from '../consumeQuota';

describe('getMaxCountForPlan', () => {
  it('returns -1 for PRO plan', () => {
    expect(getMaxCountForPlan('PRO')).toBe(-1);
  });

  it('returns FREE_PLAN_LIMIT for FREE plan', () => {
    expect(getMaxCountForPlan('FREE')).toBe(FREE_PLAN_LIMIT);
  });

  it('returns FREE_PLAN_LIMIT when plan is null (no subscription)', () => {
    expect(getMaxCountForPlan(null)).toBe(FREE_PLAN_LIMIT);
  });
});
```

**Step 2: 구현**

```typescript
// web_saas/src/lib/quota/consumeQuota.ts
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

export const FREE_PLAN_LIMIT = 10;

export function getMaxCountForPlan(plan: string | null): number {
  return plan === 'PRO' ? -1 : FREE_PLAN_LIMIT;
}

export async function consumeQuotaIfNeeded(params: {
  orgId: string;
  evaluationJobId: string;
  periodStart: Date;
}): Promise<'OK' | 'QUOTA_EXCEEDED'> {
  const { orgId, evaluationJobId, periodStart } = params;

  return await prisma.$transaction(async (tx) => {
    const job = await tx.evaluationJob.findUnique({
      where: { id: evaluationJobId },
      select: { quotaConsumed: true },
    });
    if (job?.quotaConsumed) return 'OK';

    const sub = await tx.subscription.findUnique({
      where: { organizationId: orgId },
      select: { plan: true },
    });
    const maxCount = getMaxCountForPlan(sub?.plan ?? null);

    await tx.usageQuota.upsert({
      where: { organizationId_periodStart: { organizationId: orgId, periodStart } },
      create: { id: createId(), organizationId: orgId, periodStart, usedCount: 0, maxCount },
      update: {},
    });

    if (maxCount === -1) {
      await tx.evaluationJob.update({ where: { id: evaluationJobId }, data: { quotaConsumed: true } });
      return 'OK';
    }

    const affected = await tx.$executeRaw`
      UPDATE usage_quotas
      SET used_count = used_count + 1, updated_at = NOW()
      WHERE organization_id = ${orgId}
        AND period_start = ${periodStart}
        AND used_count < max_count
    `;
    if (affected === 0) return 'QUOTA_EXCEEDED';

    await tx.evaluationJob.update({ where: { id: evaluationJobId }, data: { quotaConsumed: true } });
    return 'OK';
  });
}

/** 현재 구독 주기의 periodStart(월 첫날 UTC)를 반환 */
export function getCurrentPeriodStart(): Date {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
}
```

**Step 3: 테스트 실행**

```bash
cd web_saas && npm test -- --testPathPattern=consumeQuota
```

Expected: 3 tests PASS.

**Step 4: 커밋**

```bash
git add web_saas/src/lib/quota/
git commit -m "feat: add consumeQuotaIfNeeded with plan-aware quota row creation"
```

---

## Phase 4 — n8n 워크플로우

> n8n 워크플로우는 JSON으로 저장하고 n8n UI에서 Import함.
> 각 워크플로우의 Code Node 안에서 Prisma 대신 `pg` 직접 SQL 또는 Next.js Webhook 호출로 DB 조작.

### Task 10: `stale_lock_reclaim` 워크플로우

**Files:**
- Create: `n8n/workflows/stale_lock_reclaim.json`

**Step 1: 워크플로우 JSON 작성**

```json
{
  "name": "stale_lock_reclaim",
  "nodes": [
    {
      "name": "Schedule",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": { "rule": { "interval": [{ "field": "minutes", "minutesInterval": 5 }] } },
      "position": [240, 300]
    },
    {
      "name": "Release Stale Locks",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE evaluation_jobs SET locked_at = NULL, lock_owner = NULL WHERE locked_at < NOW() - INTERVAL '5 minutes';\nUPDATE ingestion_jobs SET locked_at = NULL, lock_owner = NULL WHERE locked_at < NOW() - INTERVAL '10 minutes';"
      },
      "position": [460, 300]
    }
  ],
  "connections": {
    "Schedule": { "main": [[{ "node": "Release Stale Locks", "type": "main", "index": 0 }]] }
  }
}
```

**Step 2: 커밋**

```bash
git add n8n/workflows/stale_lock_reclaim.json
git commit -m "feat: add stale_lock_reclaim n8n workflow"
```

---

### Task 11: `g2b_bid_crawler` 워크플로우

**Files:**
- Create: `n8n/workflows/g2b_bid_crawler.json`

**Step 1: 워크플로우 JSON 작성**

```json
{
  "name": "g2b_bid_crawler",
  "nodes": [
    {
      "name": "Schedule",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": { "rule": { "interval": [{ "field": "minutes", "minutesInterval": 30 }] } },
      "position": [100, 300]
    },
    {
      "name": "Aggregate Keywords",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT DISTINCT kw.keyword FROM organizations o JOIN subscriptions s ON s.organization_id = o.id AND s.status IN ('ACTIVE', 'TRIALING') CROSS JOIN LATERAL jsonb_array_elements_text(COALESCE(o.interest_config->'keywords', '[]'::jsonb)) AS kw(keyword);"
      },
      "position": [300, 300]
    },
    {
      "name": "Build Keyword Filter",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "const keywords = $input.all().map(i => i.json.keyword);\nreturn [{ json: { keywords, keywordParam: keywords.join(',') } }];"
      },
      "position": [500, 300]
    },
    {
      "name": "G2B OpenAPI",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://apis.data.go.kr/1230000/BidPublicInfoService04/getBidPblancListInfoThng01",
        "method": "GET",
        "queryParameters": {
          "parameters": [
            { "name": "serviceKey", "value": "={{ $env.G2B_API_KEY }}" },
            { "name": "pageNo", "value": "1" },
            { "name": "numOfRows", "value": "100" },
            { "name": "inqryDiv", "value": "1" }
          ]
        }
      },
      "position": [700, 300]
    },
    {
      "name": "Process Notices",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "const crypto = require('crypto');\nconst { createId } = require('@paralleldrive/cuid2');\n\nconst items = $input.first().json.response?.body?.items?.item ?? [];\nconst results = [];\n\nfor (const item of (Array.isArray(items) ? items : [items])) {\n  const attachmentUrl = item.ntceSpecDocUrl ?? '';\n  const modifiedAt = item.rgstDt ?? '';\n  const etag = '';\n  const lastModified = '';\n  const provisionalHash = crypto\n    .createHash('sha256')\n    .update(attachmentUrl + modifiedAt + etag + lastModified)\n    .digest('hex');\n\n  results.push({ json: {\n    source: 'g2b',\n    externalId: item.bidNtceNo,\n    title: item.bidNtceNm,\n    category: item.ntceInsttNm,\n    region: item.dminsttNm,\n    url: item.ntceSpecDocUrl,\n    publishedAt: item.rgstDt,\n    deadlineAt: item.bidClseDt,\n    attachmentUrl,\n    provisionalHash,\n    modifiedAt,\n  }});\n}\nreturn results;"
      },
      "position": [900, 300]
    },
    {
      "name": "Upsert BidNotice",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO bid_notices (id, source, external_id, title, category, region, url, published_at, deadline_at, created_at) VALUES ('{{$json.id}}', '{{$json.source}}', '{{$json.externalId}}', '{{$json.title}}', '{{$json.category}}', '{{$json.region}}', '{{$json.url}}', '{{$json.publishedAt}}', '{{$json.deadlineAt}}', NOW()) ON CONFLICT (source, external_id) DO UPDATE SET source = EXCLUDED.source RETURNING id;"
      },
      "position": [1100, 300]
    },
    {
      "name": "Insert IngestionJob",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "// n8n Code Node: INSERT ingestion_jobs with ON CONFLICT DO NOTHING\n// Uses $node[\"Upsert BidNotice\"].json.id as bidNoticeId\nconst bidNoticeId = $node[\"Upsert BidNotice\"].json.id;\nconst { provisionalHash, attachmentUrl } = $json;\nconst idempotencyKey = `${bidNoticeId}:${provisionalHash}`;\n\n// Returns SQL to execute\nreturn [{ json: { bidNoticeId, idempotencyKey, provisionalHash, attachmentUrl } }];"
      },
      "position": [1300, 300]
    },
    {
      "name": "Insert IngestionJob SQL",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO ingestion_jobs (id, bid_notice_id, status, idempotency_key, provisional_hash, attachment_url, created_at, updated_at) VALUES (gen_random_uuid()::text, '{{$json.bidNoticeId}}', 'NEW', '{{$json.idempotencyKey}}', '{{$json.provisionalHash}}', '{{$json.attachmentUrl}}', NOW(), NOW()) ON CONFLICT (idempotency_key) DO NOTHING;"
      },
      "position": [1500, 300]
    }
  ],
  "connections": {
    "Schedule": { "main": [[{ "node": "Aggregate Keywords", "type": "main", "index": 0 }]] },
    "Aggregate Keywords": { "main": [[{ "node": "Build Keyword Filter", "type": "main", "index": 0 }]] },
    "Build Keyword Filter": { "main": [[{ "node": "G2B OpenAPI", "type": "main", "index": 0 }]] },
    "G2B OpenAPI": { "main": [[{ "node": "Process Notices", "type": "main", "index": 0 }]] },
    "Process Notices": { "main": [[{ "node": "Upsert BidNotice", "type": "main", "index": 0 }]] },
    "Upsert BidNotice": { "main": [[{ "node": "Insert IngestionJob", "type": "main", "index": 0 }]] },
    "Insert IngestionJob": { "main": [[{ "node": "Insert IngestionJob SQL", "type": "main", "index": 0 }]] }
  }
}
```

> **주의**: n8n Postgres 노드에서 파라미터 바인딩은 UI에서 Expression 모드로 변경하여 SQL injection을 방지해야 함. JSON 뼈대를 import 후 UI에서 각 노드의 값을 Expression으로 설정.

**Step 2: 커밋**

```bash
git add n8n/workflows/g2b_bid_crawler.json
git commit -m "feat: add g2b_bid_crawler n8n workflow skeleton"
```

---

### Task 12: `ingestion_worker` 워크플로우

**Files:**
- Create: `n8n/workflows/ingestion_worker.json`

**Step 1: 워크플로우 JSON 작성**

```json
{
  "name": "ingestion_worker",
  "nodes": [
    {
      "name": "Schedule",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": { "rule": { "interval": [{ "field": "minutes", "minutesInterval": 2 }] } },
      "position": [100, 300]
    },
    {
      "name": "Find Candidates",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT id, bid_notice_id, attachment_url, provisional_hash, retry_count FROM ingestion_jobs WHERE ( (status = 'NEW' AND created_at < NOW() - INTERVAL '2 minutes') OR status IN ('FETCH_ERROR', 'PARSE_ERROR') ) AND locked_at IS NULL AND (next_retry_at IS NULL OR next_retry_at <= NOW()) LIMIT 5;"
      },
      "position": [300, 300]
    },
    {
      "name": "Process Each Job",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "// 각 candidate에 대해 원자 락 획득 후 처리\n// 실제 구현: HTTP Request로 Next.js /api/internal/ingestion-worker 호출\nconst workerId = `n8n-ingestion-${Date.now()}`;\nconst results = [];\n\nfor (const item of $input.all()) {\n  results.push({ json: { ...item.json, workerId } });\n}\nreturn results;"
      },
      "position": [500, 300]
    },
    {
      "name": "Atomic Lock + Process",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "={{ $env.N8N_WEBHOOK_URL }}/api/internal/process-ingestion-job",
        "method": "POST",
        "body": "={{ JSON.stringify({ jobId: $json.id, workerId: $json.workerId }) }}",
        "headers": {
          "parameters": [{ "name": "Content-Type", "value": "application/json" }]
        }
      },
      "position": [700, 300]
    }
  ],
  "connections": {
    "Schedule": { "main": [[{ "node": "Find Candidates", "type": "main", "index": 0 }]] },
    "Find Candidates": { "main": [[{ "node": "Process Each Job", "type": "main", "index": 0 }]] },
    "Process Each Job": { "main": [[{ "node": "Atomic Lock + Process", "type": "main", "index": 0 }]] }
  }
}
```

**Step 2: 커밋**

```bash
git add n8n/workflows/ingestion_worker.json
git commit -m "feat: add ingestion_worker n8n workflow"
```

---

### Task 13: `evaluation_worker` 워크플로우

**Files:**
- Create: `n8n/workflows/evaluation_worker.json`

**Step 1: 워크플로우 JSON 작성**

```json
{
  "name": "evaluation_worker",
  "nodes": [
    {
      "name": "Schedule",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": { "rule": { "interval": [{ "field": "minutes", "minutesInterval": 1 }] } },
      "position": [100, 300]
    },
    {
      "name": "Find Candidates",
      "type": "n8n-nodes-base.postgres",
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT id FROM evaluation_jobs WHERE status IN ('PENDING', 'SCORED', 'SCORE_ERROR', 'NOTIFY_ERROR') AND locked_at IS NULL AND (next_retry_at IS NULL OR next_retry_at <= NOW()) LIMIT 10;"
      },
      "position": [300, 300]
    },
    {
      "name": "Sign & Call Webhook",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "const crypto = require('crypto');\nconst workerId = `n8n-eval-${Date.now()}`;\nconst results = [];\n\nfor (const item of $input.all()) {\n  const payload = JSON.stringify({ event: 'evaluation.process', data: { jobId: item.json.id, workerId } });\n  const timestamp = Math.floor(Date.now() / 1000).toString();\n  const nonce = crypto.randomUUID();\n  const signingString = `${timestamp}.${nonce}.${payload}`;\n  const signature = crypto.createHmac('sha256', $env.WEBHOOK_SECRET).update(signingString).digest('hex');\n\n  results.push({ json: { payload, timestamp, nonce, signature } });\n}\nreturn results;"
      },
      "position": [500, 300]
    },
    {
      "name": "Call Next.js Webhook",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "={{ $env.N8N_WEBHOOK_URL }}/api/webhooks/n8n",
        "method": "POST",
        "body": "={{ $json.payload }}",
        "headers": {
          "parameters": [
            { "name": "Content-Type", "value": "application/json" },
            { "name": "X-Timestamp", "value": "={{ $json.timestamp }}" },
            { "name": "X-Nonce", "value": "={{ $json.nonce }}" },
            { "name": "X-Signature", "value": "={{ $json.signature }}" }
          ]
        }
      },
      "position": [700, 300]
    }
  ],
  "connections": {
    "Schedule": { "main": [[{ "node": "Find Candidates", "type": "main", "index": 0 }]] },
    "Find Candidates": { "main": [[{ "node": "Sign & Call Webhook", "type": "main", "index": 0 }]] },
    "Sign & Call Webhook": { "main": [[{ "node": "Call Next.js Webhook", "type": "main", "index": 0 }]] }
  }
}
```

**Step 2: 커밋**

```bash
git add n8n/workflows/evaluation_worker.json
git commit -m "feat: add evaluation_worker n8n workflow"
```

---

## Phase 5 — 잡 처리 API (Next.js)

### Task 14: 잡 처리 내부 API — Ingestion

**Files:**
- Create: `web_saas/src/app/api/internal/process-ingestion-job/route.ts`

**목적**: n8n ingestion_worker가 HTTP로 호출. 원자 락 획득 → 첨부파일 다운로드/파싱 → 상태 전이.

**Step 1: 파일 작성**

```typescript
// web_saas/src/app/api/internal/process-ingestion-job/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createEvaluationJobsForBidNotice } from '@/lib/jobs/createEvaluationJobs';
import crypto from 'crypto';

const MAX_RETRIES = 3;

function backoffMs(retryCount: number): number {
  return Math.min(60_000 * Math.pow(2, retryCount - 1), 3_600_000); // 1min, 2min, 4min ... max 1h
}

export async function POST(req: NextRequest) {
  const { jobId, workerId } = await req.json();

  // 1. 원자 락 획득
  const acquired = await prisma.$executeRaw`
    UPDATE ingestion_jobs
    SET locked_at = NOW(), lock_owner = ${workerId}
    WHERE id = ${jobId}
      AND locked_at IS NULL
  `;
  if (acquired === 0) {
    return NextResponse.json({ ok: false, reason: 'lock_not_acquired' });
  }

  const job = await prisma.ingestionJob.findUnique({ where: { id: jobId } });
  if (!job) return NextResponse.json({ ok: false, reason: 'not_found' });

  try {
    // 2. 첨부파일 다운로드
    let fileBytes: Buffer;
    try {
      const resp = await fetch(job.attachmentUrl!);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      fileBytes = Buffer.from(await resp.arrayBuffer());
    } catch (e) {
      return await handleError(jobId, 'FETCH_ERROR', e);
    }

    // 3. contentHash 계산
    const contentHash = crypto.createHash('sha256').update(fileBytes).digest('hex');

    // 4. 텍스트 파싱 (HWP/PDF → plain text)
    let attachmentText: string;
    try {
      attachmentText = fileBytes.toString('utf8'); // 실제: HWP 파서 또는 PDF 파서 적용
    } catch (e) {
      return await handleError(jobId, 'PARSE_ERROR', e);
    }

    // 5. BidNotice 텍스트 저장 + IngestionJob COMPLETED
    await prisma.$transaction([
      prisma.bidNotice.update({
        where: { id: job.bidNoticeId },
        data: { attachmentText },
      }),
      prisma.ingestionJob.update({
        where: { id: jobId },
        data: { status: 'COMPLETED', contentHash, lockedAt: null, lockOwner: null },
      }),
    ]);

    // 6. EvaluationJob 생성 (interestConfig 필터 적용)
    const notice = await prisma.bidNotice.findUnique({
      where: { id: job.bidNoticeId },
      select: { title: true, category: true, region: true },
    });
    if (notice) {
      await createEvaluationJobsForBidNotice({
        bidNoticeId: job.bidNoticeId,
        noticeRevision: contentHash,
        noticeMeta: notice,
      });
    }

    return NextResponse.json({ ok: true });
  } catch (e) {
    return await handleError(jobId, 'FETCH_ERROR', e);
  }
}

async function handleError(jobId: string, errorStatus: 'FETCH_ERROR' | 'PARSE_ERROR', _err: unknown) {
  const job = await prisma.ingestionJob.findUnique({ where: { id: jobId }, select: { retryCount: true } });
  const newRetryCount = (job?.retryCount ?? 0) + 1;

  if (newRetryCount > MAX_RETRIES) {
    await prisma.ingestionJob.update({
      where: { id: jobId },
      data: { status: 'RETRY_EXHAUSTED', retryCount: newRetryCount, lockedAt: null, lockOwner: null },
    });
  } else {
    const nextRetryAt = new Date(Date.now() + backoffMs(newRetryCount));
    await prisma.ingestionJob.update({
      where: { id: jobId },
      data: { status: errorStatus, retryCount: newRetryCount, nextRetryAt, lockedAt: null, lockOwner: null },
    });
  }

  return NextResponse.json({ ok: false, reason: errorStatus });
}
```

**Step 2: 커밋**

```bash
git add web_saas/src/app/api/internal/
git commit -m "feat: add process-ingestion-job api endpoint"
```

---

### Task 15: 잡 처리 내부 API — Evaluation

**Files:**
- Create: `web_saas/src/app/api/internal/process-evaluation-job/route.ts`

**Step 1: 파일 작성**

```typescript
// web_saas/src/app/api/internal/process-evaluation-job/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { consumeQuotaIfNeeded, getCurrentPeriodStart } from '@/lib/quota/consumeQuota';
import { Resend } from 'resend';

const FASTAPI_URL = process.env.FASTAPI_URL!;
const MAX_RETRIES = 3;
const resend = new Resend(process.env.RESEND_API_KEY);

function backoffMs(n: number) { return Math.min(60_000 * 2 ** (n - 1), 3_600_000); }

export async function POST(req: NextRequest) {
  const { jobId, workerId } = await req.json();

  const acquired = await prisma.$executeRaw`
    UPDATE evaluation_jobs
    SET locked_at = NOW(), lock_owner = ${workerId}
    WHERE id = ${jobId} AND locked_at IS NULL
  `;
  if (acquired === 0) return NextResponse.json({ ok: false, reason: 'lock_not_acquired' });

  const job = await prisma.evaluationJob.findUnique({
    where: { id: jobId },
    include: {
      bidNotice: { select: { attachmentText: true, title: true } },
      organization: { select: { companyFacts: true, name: true } },
    },
  });
  if (!job) return NextResponse.json({ ok: false, reason: 'not_found' });

  // SCORED / NOTIFY_ERROR → 이메일만 재시도
  if (job.status === 'SCORED' || job.status === 'NOTIFY_ERROR') {
    return await sendNotification(job);
  }

  // PENDING / SCORE_ERROR → 쿼터 확인 + FastAPI 호출
  const periodStart = getCurrentPeriodStart();
  const quotaResult = await consumeQuotaIfNeeded({
    orgId: job.organizationId,
    evaluationJobId: jobId,
    periodStart,
  });

  if (quotaResult === 'QUOTA_EXCEEDED') {
    await prisma.evaluationJob.update({
      where: { id: jobId },
      data: { status: 'QUOTA_EXCEEDED', lockedAt: null, lockOwner: null },
    });
    return NextResponse.json({ ok: false, reason: 'quota_exceeded' });
  }

  try {
    const resp = await fetch(`${FASTAPI_URL}/api/analyze-bid`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        organization_id: job.organizationId,
        bid_notice_id: job.bidNoticeId,
        company_facts: job.organization.companyFacts,
        attachment_text: job.bidNotice.attachmentText ?? '',
      }),
    });

    if (!resp.ok) throw new Error(`FastAPI ${resp.status}`);
    const result = await resp.json();

    await prisma.evaluationJob.update({
      where: { id: jobId },
      data: {
        status: 'SCORED',
        isEligible: result.is_eligible,
        details: result.details,
        actionPlan: result.action_plan,
        lockedAt: null,
        lockOwner: null,
      },
    });

    // 즉시 알림 시도
    const updatedJob = await prisma.evaluationJob.findUnique({ where: { id: jobId } });
    return await sendNotification(updatedJob!);
  } catch (_e) {
    return await handleScoreError(jobId);
  }
}

async function sendNotification(job: Awaited<ReturnType<typeof prisma.evaluationJob.findUnique>> & object) {
  if (!job) return NextResponse.json({ ok: false });
  const org = await prisma.organization.findUnique({ where: { id: job.organizationId }, select: { name: true } });
  const notice = await prisma.bidNotice.findUnique({ where: { id: job.bidNoticeId }, select: { title: true } });

  try {
    await resend.emails.send({
      from: 'bid-platform@yourdomain.com',
      to: `${org?.name ?? 'user'}@example.com`, // TODO: Organization에 email 필드 추가 시 교체
      subject: `[입찰분석] ${notice?.title ?? ''} — ${job.isEligible ? '입찰 가능' : '조건 부족'}`,
      text: `입찰 가능 여부: ${job.isEligible ? 'YES' : 'NO'}\n\n액션 플랜: ${job.actionPlan ?? ''}`,
      headers: { 'Idempotency-Key': job.id }, // 중복 발송 방지
    });

    await prisma.evaluationJob.update({
      where: { id: job.id },
      data: { status: 'NOTIFIED', lockedAt: null, lockOwner: null },
    });
    return NextResponse.json({ ok: true });
  } catch (_e) {
    return await handleNotifyError(job.id);
  }
}

async function handleScoreError(jobId: string) {
  const job = await prisma.evaluationJob.findUnique({ where: { id: jobId }, select: { retryCount: true } });
  const n = (job?.retryCount ?? 0) + 1;
  if (n > MAX_RETRIES) {
    await prisma.evaluationJob.update({ where: { id: jobId }, data: { status: 'RETRY_EXHAUSTED', retryCount: n, lockedAt: null, lockOwner: null } });
  } else {
    await prisma.evaluationJob.update({ where: { id: jobId }, data: { status: 'SCORE_ERROR', retryCount: n, nextRetryAt: new Date(Date.now() + backoffMs(n)), lockedAt: null, lockOwner: null } });
  }
  return NextResponse.json({ ok: false, reason: 'score_error' });
}

async function handleNotifyError(jobId: string) {
  const job = await prisma.evaluationJob.findUnique({ where: { id: jobId }, select: { retryCount: true } });
  const n = (job?.retryCount ?? 0) + 1;
  if (n > MAX_RETRIES) {
    await prisma.evaluationJob.update({ where: { id: jobId }, data: { status: 'RETRY_EXHAUSTED', retryCount: n, lockedAt: null, lockOwner: null } });
  } else {
    await prisma.evaluationJob.update({ where: { id: jobId }, data: { status: 'NOTIFY_ERROR', retryCount: n, nextRetryAt: new Date(Date.now() + backoffMs(n)), lockedAt: null, lockOwner: null } });
  }
  return NextResponse.json({ ok: false, reason: 'notify_error' });
}
```

**Step 2: Resend 패키지 설치**

```bash
cd web_saas && npm install resend
```

**Step 3: 커밋**

```bash
git add web_saas/src/app/api/internal/process-evaluation-job/
git commit -m "feat: add process-evaluation-job api with quota check and email notification"
```

---

## Phase 6 — Stripe 구독 Webhook

### Task 16: Stripe Webhook 핸들러

**Files:**
- Create: `web_saas/src/app/api/webhooks/stripe/route.ts`

**Step 1: Stripe 패키지 설치**

```bash
cd web_saas && npm install stripe
```

**Step 2: 파일 작성**

```typescript
// web_saas/src/app/api/webhooks/stripe/route.ts
import { NextRequest, NextResponse } from 'next/server';
import Stripe from 'stripe';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET!;

export async function POST(req: NextRequest) {
  const rawBody = await req.text();
  const sig = req.headers.get('stripe-signature')!;

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(rawBody, sig, webhookSecret);
  } catch (e) {
    return NextResponse.json({ error: 'invalid_signature' }, { status: 400 });
  }

  switch (event.type) {
    case 'customer.subscription.created':
    case 'customer.subscription.updated': {
      const sub = event.data.object as Stripe.Subscription;
      const orgId = sub.metadata?.organizationId;
      if (!orgId) break;

      const plan = sub.items.data[0]?.price?.nickname === 'PRO' ? 'PRO' : 'FREE';
      const status = sub.status.toUpperCase();

      await prisma.subscription.upsert({
        where: { organizationId: orgId },
        create: {
          id: createId(),
          organizationId: orgId,
          plan: plan as 'FREE' | 'PRO',
          status,
          stripeSubId: sub.id,
          currentPeriodStart: new Date(sub.current_period_start * 1000),
          currentPeriodEnd: new Date(sub.current_period_end * 1000),
        },
        update: {
          plan: plan as 'FREE' | 'PRO',
          status,
          stripeSubId: sub.id,
          currentPeriodStart: new Date(sub.current_period_start * 1000),
          currentPeriodEnd: new Date(sub.current_period_end * 1000),
        },
      });
      break;
    }

    case 'customer.subscription.deleted': {
      const sub = event.data.object as Stripe.Subscription;
      const orgId = sub.metadata?.organizationId;
      if (!orgId) break;
      await prisma.subscription.updateMany({
        where: { organizationId: orgId },
        data: { status: 'CANCELED' },
      });
      break;
    }
  }

  return NextResponse.json({ received: true });
}
```

**Step 3: 커밋**

```bash
git add web_saas/src/app/api/webhooks/stripe/
git commit -m "feat: add stripe subscription webhook handler"
```

---

## Phase 7 — 통합 테스트 & 검증

### Task 17: End-to-End 스모크 테스트

**Step 1: 전체 서비스 기동**

```bash
cp .env.example .env
# .env에서 실제 값으로 교체 후:
docker-compose up -d
```

**Step 2: PostgreSQL 마이그레이션 실행**

```bash
cd web_saas && npx prisma migrate deploy
```

**Step 3: 서비스 헬스 체크**

```bash
curl http://localhost:3000/api/health        # Next.js: {"ok":true}
curl http://localhost:8001/health            # FastAPI: {"status":"ok"}
curl http://localhost:5678/healthz           # n8n: OK
```

**Step 4: Webhook 서명 테스트**

```bash
# HMAC 서명 생성 후 webhook 호출 테스트
node -e "
const crypto = require('crypto');
const ts = Math.floor(Date.now()/1000).toString();
const nonce = crypto.randomUUID();
const body = JSON.stringify({ event: 'test', data: {} });
const sig = crypto.createHmac('sha256', 'your_webhook_secret').update(ts+'.'+nonce+'.'+body).digest('hex');
console.log('curl -X POST http://localhost:3000/api/webhooks/n8n -H Content-Type:application/json -H X-Timestamp:'+ts+' -H X-Nonce:'+nonce+' -H X-Signature:'+sig+' -d \\''+body+'\\'');
"
```

Expected: `{"ok":true}` (unknown event에 대한 경고 로그 허용)

**Step 5: n8n 워크플로우 Import**

n8n UI (http://localhost:5678) → Import from file:
- `n8n/workflows/stale_lock_reclaim.json`
- `n8n/workflows/g2b_bid_crawler.json`
- `n8n/workflows/ingestion_worker.json`
- `n8n/workflows/evaluation_worker.json`

각 워크플로우 활성화 확인.

**Step 6: 최종 커밋**

```bash
git add .
git commit -m "feat: complete bid platform phase 1-6 implementation"
```

---

## 파일 목록 요약

```
web_saas/
├── prisma/schema.prisma               (Task 2 — 교체)
├── src/
│   ├── lib/
│   │   ├── prisma.ts                  (Task 3)
│   │   ├── ids.ts                     (Task 3)
│   │   ├── errors.ts                  (Task 3)
│   │   ├── hmac.ts                    (Task 6)
│   │   ├── jobs/
│   │   │   ├── createEvaluationJobs.ts (Task 8)
│   │   │   └── __tests__/createEvaluationJobs.test.ts
│   │   └── quota/
│   │       ├── consumeQuota.ts        (Task 9)
│   │       └── __tests__/consumeQuota.test.ts
│   └── app/api/
│       ├── webhooks/
│       │   ├── n8n/route.ts           (Task 7)
│       │   └── stripe/route.ts        (Task 16)
│       └── internal/
│           ├── process-ingestion-job/route.ts (Task 14)
│           └── process-evaluation-job/route.ts (Task 15)

rag_engine/
├── requirements.txt                   (Task 4)
├── Dockerfile                         (Task 4)
├── main.py                            (Task 4)
├── models.py                          (Task 4)
├── engine.py                          (복사)
├── matcher.py                         (복사)
├── rfx_analyzer.py                    (복사)
├── response_parser.py                 (복사)
└── tests/test_analyze_bid.py          (Task 5)

n8n/workflows/
├── stale_lock_reclaim.json            (Task 10)
├── g2b_bid_crawler.json               (Task 11)
├── ingestion_worker.json              (Task 12)
└── evaluation_worker.json             (Task 13)

docker-compose.yml                     (Task 1)
.env.example                           (Task 1)
```
