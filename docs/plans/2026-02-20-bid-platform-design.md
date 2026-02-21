# B2B SaaS 입찰공고 자동 분석 플랫폼 설계

**작성일**: 2026-02-20
**브랜치**: feat/bid-platform
**상태**: 승인 완료

---

## §1. 개요 및 아키텍처

### 목적

나라장터(G2B) 공공조달 입찰에 참여하는 모든 기업이 관심 공고를 자동으로 수집·분석하고, 입찰 가능 여부와 부족 조건을 즉시 파악할 수 있도록 돕는 멀티테넌트 B2B SaaS 플랫폼.

### 핵심 컨셉

- **멀티테넌트**: `Organization` = 1 테넌트. 기업이 직접 가입하고 제원을 등록.
- **interestConfig**: 각 기업이 관심 키워드·지역을 설정 → 크롤링 필터 + 평가 대상 결정.
- **결정론적 RAG**: 면허 코드, 자본금, 지역, 인증서를 근거로 입찰 가능 여부를 Boolean으로 판정.
- **구독 티어**: Free (월 10건 평가) / Pro (무제한 평가 + 알림).

### 서비스 토폴로지 (Docker Compose)

```
┌────────────────────────────────────────────────────────┐
│  Next.js :3000  ←→  PostgreSQL :5432 (Prisma ORM)     │
│       ↕ HTTP                                           │
│  FastAPI :8001  (RAG 평가 엔진)                        │
│       ↕ Webhook (HMAC-SHA256)                          │
│  n8n    :5678  (크롤링 + 잡 워커 + 재시도)              │
└────────────────────────────────────────────────────────┘
```

**환경 변수 규칙**
- `PGTZ=UTC`, `DATABASE_URL?timezone=UTC` — 모든 서비스에서 UTC 강제.
- `Date.UTC(y, m, 1)` 사용; `new Date(year, month, 1)` 금지 (로컬 타임존 오염).

---

## §2. DB 스키마 (Prisma)

### 2-1. 열거형(Enum)

```prisma
enum IngestionJobStatus {
  NEW
  FETCH_ERROR
  PARSE_ERROR
  COMPLETED
  RETRY_EXHAUSTED   // terminal
}

enum EvaluationJobStatus {
  PENDING
  SCORED
  SCORE_ERROR
  QUOTA_EXCEEDED    // terminal
  NOTIFIED          // terminal
  NOTIFY_ERROR
  RETRY_EXHAUSTED   // terminal
}

enum PlanTier {
  FREE
  PRO
}
```

**중간 상태(FETCHING, PARSING, EVALUATING, NOTIFYING)는 DB 상태로 저장하지 않음.**
워커 내 인메모리 처리 흐름으로만 사용. DB에는 직전 안정 상태(NEW, SCORED 등)가 유지되고,
완료 또는 에러 전이 시에만 DB를 업데이트한다. 크래시 시 DB 상태 = 복구 기준점.

### 2-2. 모델

```prisma
model Organization {
  id             String        @id @default(cuid())
  name           String
  companyFacts   Json          @map("company_facts")
  /// 관심 키워드·지역 설정 — docs/json_contracts.md 참조
  interestConfig Json?         @map("interest_config")
  createdAt      DateTime      @default(now()) @map("created_at")
  updatedAt      DateTime      @updatedAt @map("updated_at")

  subscription   Subscription?
  evaluationJobs EvaluationJob[]
  @@map("organizations")
}

model Subscription {
  id                 String    @id @default(cuid())
  organizationId     String    @unique @map("organization_id")
  organization       Organization @relation(fields: [organizationId], references: [id], onDelete: Cascade)
  plan               PlanTier  @default(FREE)
  status             String    // "ACTIVE" | "TRIALING" | "CANCELED" | "PAST_DUE"
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
  /// -1 = 무제한 (Pro). Free = 10.
  maxCount       Int       @map("max_count")
  createdAt      DateTime  @default(now()) @map("created_at")
  updatedAt      DateTime  @updatedAt @map("updated_at")
  @@unique([organizationId, periodStart])
  @@map("usage_quotas")
}

model BidNotice {
  id             String    @id @default(cuid())
  source         String    // "g2b"
  externalId     String    @map("external_id")
  title          String
  category       String?   // 공고 업종/분류 — interestConfig 매칭에 사용
  region         String?   // 공고 지역 — interestConfig 매칭에 사용
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
  id              String              @id @default(cuid())
  bidNoticeId     String              @map("bid_notice_id")
  bidNotice       BidNotice           @relation(fields: [bidNoticeId], references: [id], onDelete: Cascade)
  status          IngestionJobStatus  @default(NEW)
  idempotencyKey  String              @unique @map("idempotency_key")
  /// provisionalHash = SHA256(attachmentUrl + modifiedAt + (ETag??'') + (Last-Modified??''))
  provisionalHash String              @map("provisional_hash")
  /// contentHash = SHA256(fileBytes) — 실제 다운로드 후 저장
  contentHash     String?             @map("content_hash")
  attachmentUrl   String?             @map("attachment_url")
  retryCount      Int                 @default(0) @map("retry_count")
  lockedAt        DateTime?           @map("locked_at")
  lockOwner       String?             @map("lock_owner")
  nextRetryAt     DateTime?           @map("next_retry_at")
  createdAt       DateTime            @default(now()) @map("created_at")
  updatedAt       DateTime            @updatedAt @map("updated_at")
  @@index([status, lockedAt, nextRetryAt])
  @@map("ingestion_jobs")
}

model EvaluationJob {
  id               String               @id @default(cuid())
  organizationId   String               @map("organization_id")
  organization     Organization         @relation(fields: [organizationId], references: [id], onDelete: Cascade)
  bidNoticeId      String               @map("bid_notice_id")
  bidNotice        BidNotice            @relation(fields: [bidNoticeId], references: [id], onDelete: Cascade)
  status           EvaluationJobStatus  @default(PENDING)
  /// "{orgId}:{bidNoticeId}:{noticeRevision}:{evaluationReason}"
  /// noticeRevision = contentHash (다운로드 완료) 또는 provisionalHash
  /// evaluationReason: "auto" | "manual"
  idempotencyKey   String               @unique @map("idempotency_key")
  noticeRevision   String               @map("notice_revision")
  evaluationReason String               @map("evaluation_reason")
  isEligible       Boolean?             @map("is_eligible")
  details          Json?
  actionPlan       String?              @map("action_plan") @db.Text
  /// true = 이미 쿼터 차감됨 — 재시도 시 중복 차감 방지
  quotaConsumed    Boolean              @default(false) @map("quota_consumed")
  retryCount       Int                  @default(0) @map("retry_count")
  lockedAt         DateTime?            @map("locked_at")
  lockOwner        String?              @map("lock_owner")
  nextRetryAt      DateTime?            @map("next_retry_at")
  createdAt        DateTime             @default(now()) @map("created_at")
  updatedAt        DateTime             @updatedAt @map("updated_at")
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

**ID 생성**: 앱에서 `createId()` (cuid2) 사용. DB 레벨 `gen_random_uuid()` 금지.

---

## §3. HMAC Webhook 보안

n8n → Next.js `/api/webhooks/n8n` 호출 시 적용.

### 3-1. n8n 서명 생성 순서 (순서 엄수)

```javascript
const timestamp = Math.floor(Date.now() / 1000).toString();
const nonce     = crypto.randomUUID();

// nonce를 signingString에 포함 — nonce 교체 재전송 공격 방지
const signingString = `${timestamp}.${nonce}.${payloadBody}`;
const signature     = hmacSha256(signingString, WEBHOOK_SECRET);

// 헤더: X-Timestamp, X-Nonce, X-Signature
```

**핵심**: nonce가 서명 문자열에 포함되므로 공격자가 nonce만 바꿔 재전송해도 서명 검증에서 탈락.
n8n은 nonce를 DB에 INSERT하지 않음. DB INSERT는 수신 측(Next.js)만 담당.

### 3-2. Next.js 검증 순서

```typescript
// raw body 로 읽기 (json() 금지 — body 재파싱 오염)
const rawBody   = await request.text();
const timestamp = request.headers.get('x-timestamp')!;
const nonce     = request.headers.get('x-nonce')!;
const signature = request.headers.get('x-signature')!;

// 1. timestamp 범위 확인 (±5분)
const ts = parseInt(timestamp);
if (Math.abs(Date.now() / 1000 - ts) > 300) return new Response(null, { status: 401 });

// 2. 서명 검증 (nonce 포함)
const expected = hmacSha256(`${timestamp}.${nonce}.${rawBody}`, WEBHOOK_SECRET);
if (!timingSafeEqual(expected, signature)) return new Response(null, { status: 401 });

// 3. Nonce INSERT — create-only + unique constraint catch (2단계 findUnique+create 금지)
try {
  await prisma.usedNonce.create({
    data: {
      id: createId(),
      nonce,
      expiredAt: new Date((ts + 10 * 60) * 1000),
    },
  });
} catch (e) {
  if (isUniqueConstraintError(e)) return new Response(null, { status: 409 }); // replay
  throw e;
}
```

---

## §4. n8n 워크플로우 (4종)

### 4-1. `g2b_bid_crawler` — 공고 수집

**트리거**: 매 30분 Schedule

**흐름**:

1. 공공데이터포털 G2B OpenAPI 호출 — 공고 목록 페이징.
2. **관심 키워드 집계** (JOIN + JSONB 배열 평탄화):
   ```sql
   SELECT DISTINCT kw.keyword
   FROM organizations o
   JOIN subscriptions s
     ON s.organization_id = o.id
    AND s.status IN ('ACTIVE', 'TRIALING')
   CROSS JOIN LATERAL jsonb_array_elements_text(
     COALESCE(o.interest_config->'keywords', '[]'::jsonb)
   ) AS kw(keyword);
   ```
   → 전체 조직의 키워드 합집합으로 G2B API 필터 적용. 개별 매칭은 §4-4에서 수행.

3. **BidNotice UPSERT**:
   ```sql
   INSERT INTO bid_notices (id, source, external_id, title, category, region, ...)
   VALUES (...)
   ON CONFLICT (source, external_id)
   DO UPDATE SET source = EXCLUDED.source   -- dummy update, RETURNING id 활성화
   RETURNING id;
   ```

4. `provisionalHash = SHA256(attachmentUrl + modifiedAt + (ETag ?? '') + (Last-Modified ?? ''))`

5. **IngestionJob INSERT** (`idempotencyKey = ${bidNoticeId}:${provisionalHash}`):
   ```sql
   INSERT INTO ingestion_jobs (id, bid_notice_id, status, idempotency_key, provisional_hash, ...)
   VALUES (...)
   ON CONFLICT (idempotency_key) DO NOTHING;
   ```
   - affected=1: 즉시 첨부파일 다운로드·파싱 진행.
   - affected=0: 동일 해시 잡 이미 존재 → 스킵.

6. 다운로드 완료 후 `contentHash = SHA256(fileBytes)` 저장 → COMPLETED 전이 → §4-4 호출.

### 4-2. `ingestion_worker` — 고아·재시도 워커

**트리거**: 매 2분 Schedule
**목적**: NEW 고아(age>2분) + FETCH_ERROR/PARSE_ERROR 재시도

**락 획득 (2단계 원자적)**:

```javascript
// Step 1: 후보 목록 조회 (락 없음)
const candidates = await prisma.$queryRaw`
  SELECT id FROM ingestion_jobs
  WHERE (
    (status = 'NEW'        AND created_at < NOW() - INTERVAL '2 minutes')
    OR status IN ('FETCH_ERROR', 'PARSE_ERROR')
  )
  AND locked_at IS NULL
  AND (next_retry_at IS NULL OR next_retry_at <= NOW())
  LIMIT 5
`;

// Step 2: 각 후보에 대해 개별 원자 락 획득
for (const { id } of candidates) {
  const affected = await prisma.$executeRaw`
    UPDATE ingestion_jobs
    SET locked_at = NOW(), lock_owner = ${workerId}
    WHERE id = ${id}
      AND locked_at IS NULL          -- 재검증: 동시 워커 레이스 방지
  `;
  if (affected === 0) continue;      // 다른 워커가 먼저 획득 → 스킵
  await processIngestionJob(id);
}
```

**처리 흐름 (FETCH_ERROR → 성공 시)**:
- 다운로드 성공 → 같은 실행에서 즉시 파싱 진행 → COMPLETED
  (FETCH_ERROR 성공 후 별도 실행 대기 없음)

**재시도 카운트 규칙**:
```
retryCount += 1                          // 에러 진입 시 먼저 증가
if (retryCount > maxRetries) {           // maxRetries=3 → 총 4번 시도
  status = RETRY_EXHAUSTED (terminal)
} else {
  status = FETCH_ERROR | PARSE_ERROR
  nextRetryAt = NOW() + backoff(retryCount)
}
// 모든 에러 전이(terminal 포함)에서 lockedAt=NULL, lockOwner=NULL 동시 해제
```

### 4-3. `evaluation_worker` — 평가 워커

**트리거**: 매 1분 Schedule

**락 획득 (2단계 원자적, §4-2와 동일 패턴)**:

```javascript
// Step 1: 후보 목록 조회
const candidates = await prisma.$queryRaw`
  SELECT id FROM evaluation_jobs
  WHERE status IN ('PENDING', 'SCORED', 'SCORE_ERROR', 'NOTIFY_ERROR')
  AND locked_at IS NULL
  AND (next_retry_at IS NULL OR next_retry_at <= NOW())
  LIMIT 10
`;

// Step 2: 개별 원자 락 획득
for (const { id } of candidates) {
  const affected = await prisma.$executeRaw`
    UPDATE evaluation_jobs
    SET locked_at = NOW(), lock_owner = ${workerId}
    WHERE id = ${id}
      AND locked_at IS NULL          -- 재검증: 동시 워커 레이스 방지
  `;
  if (affected === 0) continue;
  await processEvaluationJob(id);
}
```

**처리 분기**:

```
PENDING / SCORE_ERROR:
  1. consumeQuotaIfNeeded() → QUOTA_EXCEEDED(terminal) 또는 OK
  2. FastAPI POST /api/analyze-bid 호출
     → 성공: status=SCORED, isEligible/details 저장
     → 실패: retryCount+=1 → RETRY_EXHAUSTED 또는 SCORE_ERROR+nextRetryAt

SCORED / NOTIFY_ERROR:
  → FastAPI 재호출 없음 (이미 결과 있음)
  → Resend 이메일 발송
     Idempotency-Key: evaluationJob.id  (중복 방지)
     → 성공: status=NOTIFIED (terminal)
     → 실패: retryCount+=1 → RETRY_EXHAUSTED 또는 NOTIFY_ERROR+nextRetryAt
```

**모든 에러 전이**: `lockedAt=NULL, lockOwner=NULL` — terminal 여부 무관하게 항상 동시 해제.

### 4-4. `createEvaluationJobsForBidNotice` — 평가 잡 생성

**호출 시점**: IngestionJob COMPLETED 전이 직후.

**interestConfig 매칭 필터**:

```typescript
async function createEvaluationJobsForBidNotice(
  bidNotice: BidNotice,       // title, category, region 포함
  ingestionJob: IngestionJob, // contentHash, provisionalHash 포함
) {
  // 1. ACTIVE/TRIALING 조직 로드
  const orgs = await prisma.organization.findMany({
    where: { subscription: { status: { in: ['ACTIVE', 'TRIALING'] } } },
    select: { id: true, interestConfig: true },
  });

  // 2. interestConfig 키워드 + 지역 매칭
  const matchedOrgs = orgs.filter(org => {
    const config = org.interestConfig as { keywords: string[]; regions: string[] } | null;
    if (!config?.keywords?.length) return false; // 미설정 조직 제외

    const keywordMatch = config.keywords.some(kw =>
      bidNotice.title.includes(kw) || (bidNotice.category ?? '').includes(kw)
    );
    const regionMatch =
      !config.regions?.length ||
      config.regions.includes(bidNotice.region ?? '');

    return keywordMatch && regionMatch;
  });

  // 3. 매칭된 조직만 EvaluationJob 생성
  const noticeRevision = ingestionJob.contentHash ?? ingestionJob.provisionalHash;

  for (const org of matchedOrgs) {
    const idempotencyKey = `${org.id}:${bidNotice.id}:${noticeRevision}:auto`;
    await prisma.evaluationJob.upsert({
      where: { idempotencyKey },
      create: {
        id: createId(),
        organizationId: org.id,
        bidNoticeId: bidNotice.id,
        status: 'PENDING',
        idempotencyKey,
        noticeRevision,
        evaluationReason: 'auto',
      },
      update: {}, // 이미 존재하면 그대로 유지
    });
  }
}
```

**효과**: 키워드·지역 불일치 조직은 Free 쿼터 소진 없음, 알림 노이즈 없음.

### 4-5. `stale_lock_reclaim` — 지연된 락 회수

**트리거**: 매 5분 Schedule (Evaluation TTL=5분 기준)

```sql
-- Evaluation: 5분 초과
UPDATE evaluation_jobs
SET locked_at = NULL, lock_owner = NULL
WHERE locked_at < NOW() - INTERVAL '5 minutes';

-- Ingestion: 10분 초과
UPDATE ingestion_jobs
SET locked_at = NULL, lock_owner = NULL
WHERE locked_at < NOW() - INTERVAL '10 minutes';
```

**주의**: status는 변경하지 않음. lock만 해제 → 워커가 다음 주기에 재처리.
중간 상태는 DB에 저장하지 않으므로(§2-1) 고아 상태 자체가 발생하지 않음.

---

## §5. 할당량 관리 (`consumeQuotaIfNeeded`)

```typescript
async function consumeQuotaIfNeeded(
  orgId: string,
  evaluationJobId: string,
  periodStart: Date,
): Promise<'OK' | 'QUOTA_EXCEEDED'> {
  return await prisma.$transaction(async (tx) => {
    // 1. quotaConsumed 확인 — 재시도 중복 차감 방지
    const job = await tx.evaluationJob.findUnique({
      where: { id: evaluationJobId },
      select: { quotaConsumed: true },
    });
    if (job?.quotaConsumed) return 'OK';

    // 2. Subscription.plan 조회 — maxCount를 plan에 맞게 결정
    const sub = await tx.subscription.findUnique({
      where: { organizationId: orgId },
      select: { plan: true, status: true },
    });
    const maxCount = sub?.plan === 'PRO' ? -1 : FREE_PLAN_LIMIT; // -1 = 무제한

    // 3. UsageQuota 행 존재 확인 + 없으면 plan-aware 자동 생성
    //    (Stripe webhook 지연으로 행이 누락된 경우에도 올바른 maxCount로 생성)
    await tx.usageQuota.upsert({
      where: { organizationId_periodStart: { organizationId: orgId, periodStart } },
      create: {
        id: createId(),
        organizationId: orgId,
        periodStart,
        usedCount: 0,
        maxCount,           // FREE=10, PRO=-1
      },
      update: {},
    });

    const quota = await tx.usageQuota.findUniqueOrThrow({
      where: { organizationId_periodStart: { organizationId: orgId, periodStart } },
    });

    // 4. maxCount=-1(Pro)이면 무제한
    if (quota.maxCount === -1) {
      await tx.evaluationJob.update({
        where: { id: evaluationJobId },
        data: { quotaConsumed: true },
      });
      return 'OK';
    }

    // 5. 원자적 증가 (한도 초과 시 0 rows affected)
    const result = await tx.$executeRaw`
      UPDATE usage_quotas
      SET used_count = used_count + 1, updated_at = NOW()
      WHERE organization_id = ${orgId}
        AND period_start = ${periodStart}
        AND used_count < max_count
    `;
    if (result === 0) return 'QUOTA_EXCEEDED';

    await tx.evaluationJob.update({
      where: { id: evaluationJobId },
      data: { quotaConsumed: true },
    });
    return 'OK';
  });
}
```

**할당량 정책**:
- 요청 기반 차감: FastAPI 호출 전에 차감. 호출 실패해도 차감됨.
- `quotaConsumed=true`이면 재시도 시 추가 차감 없음.
- Stripe webhook 지연 시에도 `sub.plan` 기반으로 올바른 `maxCount` 설정 보장.

---

## §6. FastAPI 엔드포인트

### `POST /api/analyze-bid`

```python
class AnalyzeBidRequest(BaseModel):
    organization_id: str
    bid_notice_id: str
    company_facts: dict      # Organization.companyFacts
    attachment_text: str     # BidNotice.attachmentText

class AnalyzeBidResponse(BaseModel):
    is_eligible: bool
    details: dict            # NoticeScore.details — docs/json_contracts.md §2
    action_plan: str
```

기존 `rfx_analyzer.py`, `matcher.py`, `engine.py` 로직을 FastAPI로 래핑.

---

## §7. interestConfig JSON 구조

```typescript
interface InterestConfig {
  keywords: string[];  // 예: ["CCTV", "정보통신"]
  regions:  string[];  // 예: ["경기도"] — 빈 배열 = 전국
}
```

`companyFacts` 전체 구조는 `docs/json_contracts.md §1` 참조.

---

## §8. 결정 사항 요약

| 항목 | 결정 |
|---|---|
| 중간 상태 (FETCHING 등) | DB 저장 안 함 — 인메모리만. 크래시 시 직전 안정 상태로 복구 |
| ID 생성 | `createId()` (cuid2, 앱 레벨) — `gen_random_uuid()` 금지 |
| 락 전략 | SELECT 후보 → 개별 `UPDATE WHERE id=? AND locked_at IS NULL` + affected 검사 |
| FOR UPDATE SKIP LOCKED | 금지 |
| HMAC 서명 문자열 | `${timestamp}.${nonce}.${rawBody}` — nonce 포함으로 교체 공격 차단 |
| Nonce DB 삽입 | Next.js(수신 측)만. create-only + unique constraint catch |
| 쿼터 차감 | 요청 기반, `quotaConsumed` 필드로 재시도 중복 방지 |
| UsageQuota 자동 생성 | 같은 트랜잭션에서 `sub.plan` 조회 후 PRO=-1 / FREE=10 설정 |
| 이메일 중복 방지 | `Resend Idempotency-Key: evaluationJob.id` |
| IngestionJob 중복 | `idempotencyKey = bidNoticeId:provisionalHash` — `ON CONFLICT DO NOTHING` |
| EvaluationJob 중복 | `idempotencyKey = orgId:bidNoticeId:noticeRevision:reason` — upsert (update: {}) |
| BidNotice UPSERT | `ON CONFLICT DO UPDATE SET source=EXCLUDED.source RETURNING id` |
| 첨부파일 해시 | `provisionalHash = SHA256(url+modifiedAt+ETag+LastModified)` → `contentHash = SHA256(fileBytes)` |
| 평가 대상 필터 | interestConfig 키워드+지역 매칭 조직만 EvaluationJob 생성 |
| 키워드 집계 SQL | JOIN subscriptions + `jsonb_array_elements_text` + DISTINCT |
| stale lock 처리 | lock만 해제, status 변경 없음 |
| 에러 락 해제 | terminal/non-terminal 무관 모든 에러 전이에서 `lockedAt=NULL, lockOwner=NULL` |
| UTC 강제 | `PGTZ=UTC`, `DATABASE_URL?timezone=UTC`, `Date.UTC()` 사용 |
| 재시도 카운트 | 에러 진입 시 먼저 `+=1`, 이후 `> maxRetries` 검사 |
| maxRetries 기본값 | 3 → 총 4번 시도 |
| 락 TTL | Ingestion 10분, Evaluation 5분 |
| stale_lock_reclaim 주기 | 5분 (Evaluation TTL 기준) |

---

## §9. 구현 단계 (Phase 순서)

1. **Phase 1**: Prisma 스키마 마이그레이션 (`prisma migrate dev`)
2. **Phase 2**: FastAPI 마이크로서비스 초기화 (`rag_engine/`)
3. **Phase 3**: n8n 워크플로우 4종 JSON 작성 (`n8n/`)
4. **Phase 4**: Next.js Webhook 수신 + 잡 상태 업데이트 API
5. **Phase 5**: Stripe 구독, Resend 이메일, 프론트엔드 대시보드
