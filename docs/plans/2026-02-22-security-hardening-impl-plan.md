# Security Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 발견된 8개 취약점(IDOR, CSRF, SSRF, 내부 API 노출, DoS, 비밀키 노출, 비트랜잭션 상태전이, 쿼리 로그)을 5개 Wave로 순차 수정한다.

**Architecture:** env.ts(zod 부팅 검증) → safe-fetch(SSRF) → internal-auth(HMAC) → NextAuth + middleware(세션/CSRF) → IDOR 제거 → 트랜잭션 강화 → 회귀 테스트

**Tech Stack:** Next.js 16 App Router, next-auth@5, zod, bcryptjs, Prisma 5, Jest 30, 기존 lib/hmac.ts 패턴

---

## Wave 1 (C): 즉각 수정 — 환경변수 / DoS / 로그

### Task 1: env.ts — zod 부팅 검증

**패키지 설치:**
```bash
cd web_saas && npm install zod --cache /tmp/npm-cache
```

**Files:**
- Create: `web_saas/src/lib/env.ts`
- Create: `web_saas/src/lib/__tests__/env.test.ts`

**Step 1: 실패하는 테스트 작성**

```typescript
// web_saas/src/lib/__tests__/env.test.ts
import { _resetEnv, getEnv } from '../env';

const REQUIRED_VARS = {
  DATABASE_URL: 'postgresql://x',
  STRIPE_SECRET_KEY: 'sk_test_abc',
  STRIPE_WEBHOOK_SECRET: 'whsec_abc',
  WEBHOOK_SECRET: 'a'.repeat(32),
  INTERNAL_API_SECRET: 'b'.repeat(32),
  NEXTAUTH_SECRET: 'c'.repeat(32),
  NEXTAUTH_URL: 'http://localhost:3000',
};

beforeEach(() => {
  _resetEnv();
  // Clear all required vars
  Object.keys(REQUIRED_VARS).forEach((k) => delete process.env[k]);
});

afterEach(() => {
  _resetEnv();
});

it('필수 변수 누락 시 ZodError throw', () => {
  expect(() => getEnv()).toThrow(/startup validation failed/);
});

it('모든 필수 변수 있으면 통과', () => {
  Object.assign(process.env, REQUIRED_VARS);
  const env = getEnv();
  expect(env.DATABASE_URL).toBe('postgresql://x');
  expect(env.FASTAPI_URL).toBe('http://localhost:8001'); // default
});

it('WEBHOOK_SECRET 32자 미만이면 실패', () => {
  Object.assign(process.env, { ...REQUIRED_VARS, WEBHOOK_SECRET: 'short' });
  expect(() => getEnv()).toThrow();
});
```

**Step 2: 테스트 실행 — 실패 확인**
```bash
cd web_saas && npx jest src/lib/__tests__/env.test.ts --no-coverage
```
기대: FAIL (env 모듈 없음)

**Step 3: env.ts 구현**

```typescript
// web_saas/src/lib/env.ts
import { z } from 'zod';

const schema = z.object({
  DATABASE_URL: z.string().min(1, 'DATABASE_URL is required'),
  STRIPE_SECRET_KEY: z.string().min(1, 'STRIPE_SECRET_KEY is required'),
  STRIPE_WEBHOOK_SECRET: z.string().min(1, 'STRIPE_WEBHOOK_SECRET is required'),
  WEBHOOK_SECRET: z.string().min(32, 'WEBHOOK_SECRET must be >= 32 chars'),
  INTERNAL_API_SECRET: z.string().min(32, 'INTERNAL_API_SECRET must be >= 32 chars'),
  NEXTAUTH_SECRET: z.string().min(32, 'NEXTAUTH_SECRET must be >= 32 chars'),
  NEXTAUTH_URL: z.string().url('NEXTAUTH_URL must be a valid URL'),
  FASTAPI_URL: z.string().url().default('http://localhost:8001'),
  ATTACHMENT_ALLOWED_DOMAINS: z.string().default('.go.kr'),
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
});

export type Env = z.infer<typeof schema>;

let _env: Env | undefined;

export function getEnv(): Env {
  if (!_env) {
    const result = schema.safeParse(process.env);
    if (!result.success) {
      const messages = result.error.issues
        .map((i) => `  ${i.path.join('.')}: ${i.message}`)
        .join('\n');
      throw new Error(`[env] startup validation failed:\n${messages}`);
    }
    _env = result.data;
  }
  return _env;
}

/** 테스트에서만 사용 — env 캐시 초기화 */
export function _resetEnv(): void {
  _env = undefined;
}
```

**Step 4: 테스트 실행 — 통과 확인**
```bash
cd web_saas && npx jest src/lib/__tests__/env.test.ts --no-coverage
```
기대: PASS (3/3)

**Step 5: stripe/route.ts에서 env.ts 사용 (webhookSecret 빈값 방지)**

`web_saas/src/app/api/webhooks/stripe/route.ts` 상단 수정:
```typescript
// 기존
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? 'sk_test_placeholder');
const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET ?? '';

// 변경 후 (파일 상단에 import 추가)
import { getEnv } from '@/lib/env';
// ...함수 내부가 아닌 모듈 레벨에서는 사용하지 말고 POST handler 내부에서 호출
// 아래처럼 lazy 초기화로 변경:
let _stripe: Stripe | null = null;
function getStripe(): Stripe {
  const env = getEnv();
  if (!_stripe) _stripe = new Stripe(env.STRIPE_SECRET_KEY);
  return _stripe;
}

// POST 핸들러 내부:
// const env = getEnv();
// event = getStripe().webhooks.constructEvent(rawBody, sig, env.STRIPE_WEBHOOK_SECRET);
```

**Step 6: 커밋**
```bash
cd web_saas && git add src/lib/env.ts src/lib/__tests__/env.test.ts src/app/api/webhooks/stripe/route.ts
git commit -m "feat(security): add zod env validation + fix stripe secret fallback (C-1)"
```

---

### Task 2: 입력 크기 제한 + Prisma 로그 레벨

**Files:**
- Modify: `web_saas/src/app/api/search/bids/route.ts`
- Modify: `web_saas/src/app/api/evaluate/batch/route.ts`
- Modify: `web_saas/src/lib/prisma.ts`

**Step 1: 기존 테스트 확인**
```bash
cd web_saas && npx jest src/lib/search/__tests__/buildSearchQuery.test.ts --no-coverage
```
기대: PASS (5/5) — 기존 테스트 깨지지 않음 확인

**Step 2: 입력 제한 적용**

`search/bids/route.ts` 수정 (기존 POST 핸들러 내부):
```typescript
// 기존
take: body.limit ?? 50,

// 변경
take: Math.min(Number(body.limit ?? 50), 100),
```

`evaluate/batch/route.ts` 수정:
```typescript
// 기존
if (!bidNoticeIds?.length || !organizationId) {

// 변경 (organizationId는 Task 9에서 세션으로 교체. 지금은 크기 제한만)
if (!bidNoticeIds?.length || bidNoticeIds.length > 50 || !organizationId) {
  return NextResponse.json(
    { error: 'bidNoticeIds: 1–50 items required' },
    { status: 400 }
  );
}
```

**Step 3: Prisma 로그 레벨 수정**

`web_saas/src/lib/prisma.ts` 전체 교체:
```typescript
import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === 'production' ? ['error'] : ['query', 'error', 'warn'],
  });

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
```

**Step 4: 커밋**
```bash
cd web_saas && git add src/app/api/search/bids/route.ts src/app/api/evaluate/batch/route.ts src/lib/prisma.ts
git commit -m "feat(security): cap input limits, fix prisma log level in production (C-2, C-4)"
```

---

### Task 3: safe-fetch.ts — SSRF 방어

**Files:**
- Create: `web_saas/src/lib/__tests__/safeFetch.test.ts`
- Create: `web_saas/src/lib/safe-fetch.ts`
- Modify: `web_saas/src/app/api/internal/process-ingestion-job/route.ts`

**Step 1: 실패하는 테스트 작성**

```typescript
// web_saas/src/lib/__tests__/safeFetch.test.ts
import { safeFetch } from '../safe-fetch';

// dns와 fetch를 모킹
jest.mock('dns', () => ({
  promises: {
    lookup: jest.fn(),
  },
}));

import dns from 'dns';
const mockLookup = dns.promises.lookup as jest.Mock;

const ALLOWED = ['.go.kr'];

beforeEach(() => jest.clearAllMocks());

it('http:// 스킴은 거부', async () => {
  await expect(safeFetch('http://www.g2b.go.kr/file.hwp', ALLOWED)).rejects.toThrow('only https allowed');
});

it('allowlist 외 도메인 거부', async () => {
  mockLookup.mockResolvedValue({ address: '1.2.3.4', family: 4 });
  await expect(safeFetch('https://evil.com/file.hwp', ALLOWED)).rejects.toThrow('not in allowlist');
});

it('private IP (127.x) 거부', async () => {
  mockLookup.mockResolvedValue({ address: '127.0.0.1', family: 4 });
  await expect(safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED)).rejects.toThrow('private IP');
});

it('AWS metadata IP 거부 (169.254.x)', async () => {
  mockLookup.mockResolvedValue({ address: '169.254.169.254', family: 4 });
  await expect(safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED)).rejects.toThrow('private IP');
});

it('유효한 공개 IP + 허용 도메인 → fetch 호출', async () => {
  mockLookup.mockResolvedValue({ address: '1.2.3.4', family: 4 });
  const mockResponse = { status: 200, headers: new Headers(), arrayBuffer: jest.fn().mockResolvedValue(new ArrayBuffer(0)) };
  global.fetch = jest.fn().mockResolvedValue(mockResponse);
  const res = await safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED);
  expect(res.status).toBe(200);
  expect(global.fetch).toHaveBeenCalledWith(
    'https://www.g2b.go.kr/file.hwp',
    expect.objectContaining({ redirect: 'manual' })
  );
});

it('3xx 리다이렉트는 거부', async () => {
  mockLookup.mockResolvedValue({ address: '1.2.3.4', family: 4 });
  global.fetch = jest.fn().mockResolvedValue({ status: 301, headers: new Headers() });
  await expect(safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED)).rejects.toThrow('redirect blocked');
});
```

**Step 2: 테스트 실행 — 실패 확인**
```bash
cd web_saas && npx jest src/lib/__tests__/safeFetch.test.ts --no-coverage
```
기대: FAIL

**Step 3: safe-fetch.ts 구현**

```typescript
// web_saas/src/lib/safe-fetch.ts
import dns from 'dns';

const PRIVATE_RANGES: [number, number][] = [
  [0x7f000000, 0x7fffffff], // 127.0.0.0/8 loopback
  [0x0a000000, 0x0affffff], // 10.0.0.0/8
  [0xac100000, 0xac1fffff], // 172.16.0.0/12
  [0xc0a80000, 0xc0a8ffff], // 192.168.0.0/16
  [0xa9fe0000, 0xa9feffff], // 169.254.0.0/16 (link-local / AWS metadata)
  [0xe0000000, 0xefffffff], // 224.0.0.0/4 multicast
  [0x00000000, 0x00ffffff], // 0.0.0.0/8
];

function ipv4ToInt(ip: string): number {
  return ip.split('.').reduce((acc, part) => (acc << 8) + parseInt(part, 10), 0) >>> 0;
}

function isPrivateIp(ip: string): boolean {
  if (ip === '::1') return true; // IPv6 loopback
  if (!ip.includes('.')) return false; // non-loopback IPv6: pass
  const n = ipv4ToInt(ip);
  return PRIVATE_RANGES.some(([start, end]) => n >= start && n <= end);
}

/**
 * SSRF 방어 fetch 래퍼.
 * - https 스킴만 허용
 * - allowedDomains allowlist 검사 (e.g. ['.go.kr'])
 * - DNS 사전 해석 후 private IP 차단
 * - 리다이렉트 차단 (redirect: 'manual')
 * - 10초 타임아웃
 */
export async function safeFetch(
  url: string,
  allowedDomains: string[],
  maxBytes = 50 * 1024 * 1024
): Promise<Response> {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error('SSRF: invalid URL');
  }

  // 1. HTTPS only
  if (parsed.protocol !== 'https:') {
    throw new Error(`SSRF: only https allowed, got ${parsed.protocol}`);
  }

  // 2. Domain allowlist
  const hostname = parsed.hostname.toLowerCase();
  const inAllowlist = allowedDomains.some((d) => {
    const domain = d.startsWith('.') ? d : `.${d}`;
    return hostname === d.replace(/^\./, '') || hostname.endsWith(domain);
  });
  if (!inAllowlist) {
    throw new Error(`SSRF: hostname ${hostname} not in allowlist`);
  }

  // 3. DNS 사전 해석 + private IP 차단
  const { address } = await dns.promises.lookup(hostname, { family: 4 });
  if (isPrivateIp(address)) {
    throw new Error(`SSRF: resolved to private IP ${address}`);
  }

  // 4. Content-Length 사전 차단 (요청 전)
  // (응답 후 재검증은 Step 7에서)

  // 5. Fetch — redirect 차단, 10초 타임아웃
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10_000);
  let response: Response;
  try {
    response = await fetch(url, {
      redirect: 'manual',
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }

  // 6. 3xx 리다이렉트 차단
  if (response.status >= 300 && response.status < 400) {
    throw new Error(`SSRF: redirect blocked (${response.status})`);
  }

  // 7. 응답 크기 사전 차단
  const contentLength = response.headers.get('content-length');
  if (contentLength && parseInt(contentLength, 10) > maxBytes) {
    throw new Error(`SSRF: content-length ${contentLength} exceeds ${maxBytes} bytes`);
  }

  return response;
}
```

**Step 4: 테스트 실행 — 통과 확인**
```bash
cd web_saas && npx jest src/lib/__tests__/safeFetch.test.ts --no-coverage
```
기대: PASS (6/6)

**Step 5: process-ingestion-job에 safeFetch 적용**

`web_saas/src/app/api/internal/process-ingestion-job/route.ts` 수정:

```typescript
// 상단에 import 추가
import { safeFetch } from '@/lib/safe-fetch';
import { getEnv } from '@/lib/env';

// 기존 (34번째 줄 근처)
// const resp = await fetch(job.attachmentUrl!);

// 변경
const env = getEnv();
const allowedDomains = env.ATTACHMENT_ALLOWED_DOMAINS.split(',').map((d) => d.trim());
const resp = await safeFetch(job.attachmentUrl!, allowedDomains);
```

**Step 6: 전체 테스트 확인**
```bash
cd web_saas && npx jest --no-coverage
```
기대: 전체 PASS

**Step 7: 커밋**
```bash
cd web_saas && git add src/lib/safe-fetch.ts src/lib/__tests__/safeFetch.test.ts src/app/api/internal/process-ingestion-job/route.ts
git commit -m "feat(security): add safeFetch SSRF defense + apply to ingestion job (C-3)"
```

---

## Wave 2 (B): 내부 API HMAC 보호

### Task 4: internal-auth.ts + 모든 /api/internal/* 적용

**Files:**
- Create: `web_saas/src/lib/__tests__/internalAuth.test.ts`
- Create: `web_saas/src/lib/internal-auth.ts`
- Modify: `web_saas/src/__mocks__/prisma.ts` (usedNonce mock 추가)
- Modify: `web_saas/src/app/api/internal/process-evaluation-job/route.ts`
- Modify: `web_saas/src/app/api/internal/process-ingestion-job/route.ts`
- Modify: `web_saas/src/app/api/internal/evaluation-jobs/route.ts`

**Step 1: prisma mock에 usedNonce 추가**

`web_saas/src/__mocks__/prisma.ts`:
```typescript
export const prisma = {
  $transaction: jest.fn(),
  $executeRaw: jest.fn(),
  evaluationJob: {
    findUnique: jest.fn(),
    update: jest.fn(),
    upsert: jest.fn(),
    findMany: jest.fn(),
  },
  subscription: { findUnique: jest.fn() },
  usageQuota: { upsert: jest.fn() },
  organization: { findMany: jest.fn(), findUnique: jest.fn() },
  usedNonce: { create: jest.fn() },
};
```

**Step 2: 실패하는 테스트 작성**

```typescript
// web_saas/src/lib/__tests__/internalAuth.test.ts
import { createHmac } from 'crypto';
import { NextRequest } from 'next/server';
import { verifyInternalAuth } from '../internal-auth';
import { prisma } from '@/lib/prisma';

const SECRET = 'a'.repeat(32);
const ORIGINAL_ENV = process.env.INTERNAL_API_SECRET;

beforeAll(() => { process.env.INTERNAL_API_SECRET = SECRET; });
afterAll(() => { process.env.INTERNAL_API_SECRET = ORIGINAL_ENV; });
beforeEach(() => jest.clearAllMocks());

function makeRequest(overrides: {
  ts?: string;
  nonce?: string;
  signature?: string;
  body?: string;
}): NextRequest {
  const body = overrides.body ?? '{"jobId":"j1"}';
  const ts = overrides.ts ?? String(Math.floor(Date.now() / 1000));
  const nonce = overrides.nonce ?? 'unique-nonce-1';
  const signingString = `${ts}.${nonce}.${body}`;
  const signature = overrides.signature
    ?? createHmac('sha256', SECRET).update(signingString).digest('hex');

  return new NextRequest('http://localhost/api/internal/test', {
    method: 'POST',
    headers: {
      'x-internal-timestamp': ts,
      'x-internal-nonce': nonce,
      'x-internal-signature': signature,
    },
    body,
  });
}

it('유효한 서명 → null 반환 (통과)', async () => {
  (prisma.usedNonce.create as jest.Mock).mockResolvedValue({});
  const req = makeRequest({});
  const result = await verifyInternalAuth(req, '{"jobId":"j1"}');
  expect(result).toBeNull();
});

it('타임스탬프 범위 초과 → 401', async () => {
  const req = makeRequest({ ts: '1000' }); // 2001년
  const result = await verifyInternalAuth(req, '{"jobId":"j1"}');
  expect(result?.status).toBe(401);
});

it('잘못된 서명 → 401', async () => {
  const req = makeRequest({ signature: 'deadbeef'.repeat(8) });
  const result = await verifyInternalAuth(req, '{"jobId":"j1"}');
  expect(result?.status).toBe(401);
});

it('nonce 재사용 → 409', async () => {
  const { Prisma } = jest.requireActual('@prisma/client');
  const p2002 = new Prisma.PrismaClientKnownRequestError('dup', {
    code: 'P2002',
    clientVersion: '5.0.0',
  });
  (prisma.usedNonce.create as jest.Mock).mockRejectedValue(p2002);
  const req = makeRequest({});
  const result = await verifyInternalAuth(req, '{"jobId":"j1"}');
  expect(result?.status).toBe(409);
});
```

**Step 3: 테스트 실행 — 실패 확인**
```bash
cd web_saas && npx jest src/lib/__tests__/internalAuth.test.ts --no-coverage
```
기대: FAIL

**Step 4: internal-auth.ts 구현**

```typescript
// web_saas/src/lib/internal-auth.ts
import { createHmac, timingSafeEqual } from 'crypto';
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';
import { isUniqueConstraintError } from '@/lib/errors';

const REPLAY_WINDOW_SEC = 300; // ±5분

/**
 * 내부 API HMAC 검증.
 * lib/hmac.ts의 verifyWebhookSignature와 동일 패턴.
 *
 * @param req - NextRequest (헤더에서 ts/nonce/signature 읽음)
 * @param rawBody - 이미 소비된 raw body 문자열 (GET이면 '')
 * @returns null이면 통과, NextResponse이면 에러 응답
 */
export async function verifyInternalAuth(
  req: NextRequest,
  rawBody: string
): Promise<NextResponse | null> {
  const ts = req.headers.get('x-internal-timestamp') ?? '';
  const nonce = req.headers.get('x-internal-nonce') ?? '';
  const signature = req.headers.get('x-internal-signature') ?? '';
  const secret = process.env.INTERNAL_API_SECRET ?? '';

  // 1. Timestamp window
  const tsNum = parseInt(ts, 10);
  if (!tsNum || Math.abs(Date.now() / 1000 - tsNum) > REPLAY_WINDOW_SEC) {
    return NextResponse.json({ error: 'timestamp_out_of_range' }, { status: 401 });
  }

  // 2. HMAC 서명 검증 (상수시간 비교)
  const signingString = `${ts}.${nonce}.${rawBody}`;
  const expected = createHmac('sha256', secret).update(signingString).digest('hex');
  let valid: boolean;
  try {
    valid = timingSafeEqual(Buffer.from(expected, 'hex'), Buffer.from(signature, 'hex'));
  } catch {
    valid = false;
  }
  if (!valid) {
    return NextResponse.json({ error: 'invalid_signature' }, { status: 401 });
  }

  // 3. Nonce 중복 방지 (기존 UsedNonce 테이블 재사용)
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

  return null;
}
```

**Step 5: 테스트 실행 — 통과 확인**
```bash
cd web_saas && npx jest src/lib/__tests__/internalAuth.test.ts --no-coverage
```
기대: PASS (4/4)

**Step 6: process-evaluation-job에 HMAC 적용**

`web_saas/src/app/api/internal/process-evaluation-job/route.ts` 수정:
```typescript
// 상단 import에 추가
import { verifyInternalAuth } from '@/lib/internal-auth';

// 기존 POST 핸들러 시작 부분 변경
export async function POST(req: NextRequest) {
  const rawBody = await req.text(); // body를 먼저 읽어야 HMAC 검증 가능

  const authError = await verifyInternalAuth(req, rawBody);
  if (authError) return authError;

  const { jobId, workerId } = JSON.parse(rawBody) as { jobId: string; workerId: string };
  // ... 이하 기존 코드 그대로
```

**Step 7: process-ingestion-job에 HMAC 적용**

`web_saas/src/app/api/internal/process-ingestion-job/route.ts` 수정 (동일 패턴):
```typescript
import { verifyInternalAuth } from '@/lib/internal-auth';

export async function POST(req: NextRequest) {
  const rawBody = await req.text();

  const authError = await verifyInternalAuth(req, rawBody);
  if (authError) return authError;

  const { jobId, workerId } = JSON.parse(rawBody) as { jobId: string; workerId: string };
  // ... 이하 기존 코드 그대로
```

**Step 8: evaluation-jobs GET에 HMAC 적용**

`web_saas/src/app/api/internal/evaluation-jobs/route.ts` 수정:
```typescript
import { verifyInternalAuth } from '@/lib/internal-auth';

export async function GET(req: NextRequest) {
  // GET은 body 없음 → rawBody = ''
  const authError = await verifyInternalAuth(req, '');
  if (authError) return authError;

  const { searchParams } = new URL(req.url);
  // ... 이하 기존 코드 그대로
```

**Step 9: 전체 테스트 확인**
```bash
cd web_saas && npx jest --no-coverage
```
기대: 전체 PASS

**Step 10: 커밋**
```bash
cd web_saas && git add src/lib/internal-auth.ts src/lib/__tests__/internalAuth.test.ts src/__mocks__/prisma.ts src/app/api/internal/
git commit -m "feat(security): add HMAC auth for all /api/internal/* routes (B)"
```

---

## Wave 3 (A): NextAuth + middleware + CSRF + IDOR 제거

### Task 5: User 모델 추가 (Prisma schema + 수동 마이그레이션)

**Files:**
- Modify: `web_saas/prisma/schema.prisma`
- Create: `web_saas/prisma/migrations/20260222000003_add_user/migration.sql`

**Step 1: schema.prisma에 User 모델 추가**

`Organization` 모델 끝에 relation 추가:
```prisma
// Organization 모델 내부에 추가
users          User[]
```

파일 하단에 User 모델 추가:
```prisma
model User {
  id             String       @id
  email          String       @unique
  passwordHash   String       @map("password_hash")
  organizationId String       @map("organization_id")
  organization   Organization @relation(fields: [organizationId], references: [id], onDelete: Cascade)
  createdAt      DateTime     @default(now()) @map("created_at")

  @@map("users")
}
```

**Step 2: 수동 마이그레이션 SQL 생성**

```sql
-- web_saas/prisma/migrations/20260222000003_add_user/migration.sql

CREATE TABLE "users" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "password_hash" TEXT NOT NULL,
    "organization_id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

ALTER TABLE "users" ADD CONSTRAINT "users_organization_id_fkey"
    FOREIGN KEY ("organization_id") REFERENCES "organizations"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;
```

**Step 3: Prisma 클라이언트 재생성**
```bash
cd web_saas && npx prisma generate
```
기대: 오류 없이 완료 (DB 연결 없어도 generate는 가능)

**Step 4: 커밋**
```bash
cd web_saas && git add prisma/schema.prisma prisma/migrations/20260222000003_add_user/
git commit -m "feat(db): add User model with organizationId FK (auth prerequisite)"
```

---

### Task 6: NextAuth 설치 + auth.ts + route handler

**패키지 설치:**
```bash
cd web_saas && npm install next-auth@5 bcryptjs @types/bcryptjs --cache /tmp/npm-cache
```

**Files:**
- Create: `web_saas/src/auth.ts`
- Create: `web_saas/src/app/api/auth/[...nextauth]/route.ts`
- Create: `web_saas/src/types/next-auth.d.ts`

**Step 1: NextAuth 타입 확장**

```typescript
// web_saas/src/types/next-auth.d.ts
import 'next-auth';

declare module 'next-auth' {
  interface Session {
    user: {
      id: string;
      email: string;
      organizationId: string;
    };
  }
  interface User {
    organizationId: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    organizationId: string;
  }
}
```

**Step 2: auth.ts 구현**

```typescript
// web_saas/src/auth.ts
import NextAuth from 'next-auth';
import Credentials from 'next-auth/providers/credentials';
import bcrypt from 'bcryptjs';
import { prisma } from '@/lib/prisma';

export const { auth, handlers, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;

        const user = await prisma.user.findUnique({
          where: { email: String(credentials.email) },
        });
        if (!user) return null;

        const valid = await bcrypt.compare(String(credentials.password), user.passwordHash);
        if (!valid) return null;

        return { id: user.id, email: user.email, organizationId: user.organizationId };
      },
    }),
  ],
  session: { strategy: 'jwt' },
  callbacks: {
    jwt({ token, user }) {
      if (user) token.organizationId = user.organizationId;
      return token;
    },
    session({ session, token }) {
      session.user.organizationId = token.organizationId;
      return session;
    },
  },
});
```

**Step 3: NextAuth route handler**

```typescript
// web_saas/src/app/api/auth/[...nextauth]/route.ts
import { handlers } from '@/auth';
export const { GET, POST } = handlers;
```

**Step 4: 빌드 오류 없는지 확인**
```bash
cd web_saas && npx tsc --noEmit 2>&1 | head -30
```
기대: 타입 오류 없음 (또는 next-auth 관련 타입만)

**Step 5: 커밋**
```bash
cd web_saas && git add src/auth.ts src/app/api/auth/ src/types/next-auth.d.ts
git commit -m "feat(auth): add NextAuth v5 with Credentials provider + session organizationId"
```

---

### Task 7: csrf.ts + 테스트

**Files:**
- Create: `web_saas/src/lib/__tests__/csrf.test.ts`
- Create: `web_saas/src/lib/csrf.ts`

**Step 1: 실패하는 테스트 작성**

```typescript
// web_saas/src/lib/__tests__/csrf.test.ts
import { verifyCsrfOrigin } from '../csrf';
import { NextRequest } from 'next/server';

const APP_URL = 'https://app.kirabot.kr';
const ORIGINAL_ENV = process.env.NEXT_PUBLIC_APP_URL;

beforeAll(() => { process.env.NEXT_PUBLIC_APP_URL = APP_URL; });
afterAll(() => { process.env.NEXT_PUBLIC_APP_URL = ORIGINAL_ENV; });

function req(method: string, origin: string | null): NextRequest {
  const headers: Record<string, string> = {};
  if (origin !== null) headers['origin'] = origin;
  return new NextRequest('http://localhost/api/test', { method, headers });
}

it('GET 요청은 origin 무관 통과', () => {
  expect(verifyCsrfOrigin(req('GET', 'https://evil.com'))).toBe(true);
  expect(verifyCsrfOrigin(req('GET', null))).toBe(true);
});

it('POST — 허용 origin 통과', () => {
  expect(verifyCsrfOrigin(req('POST', APP_URL))).toBe(true);
});

it('POST — 다른 origin 거부', () => {
  expect(verifyCsrfOrigin(req('POST', 'https://evil.com'))).toBe(false);
});

it('POST — origin 헤더 없으면 거부', () => {
  expect(verifyCsrfOrigin(req('POST', null))).toBe(false);
});

it('DELETE — 허용 origin 통과', () => {
  expect(verifyCsrfOrigin(req('DELETE', APP_URL))).toBe(true);
});
```

**Step 2: 테스트 실행 — 실패 확인**
```bash
cd web_saas && npx jest src/lib/__tests__/csrf.test.ts --no-coverage
```
기대: FAIL

**Step 3: csrf.ts 구현**

```typescript
// web_saas/src/lib/csrf.ts
import { NextRequest } from 'next/server';

const STATE_CHANGING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function getAllowedOrigins(): string[] {
  const appUrl = (process.env.NEXT_PUBLIC_APP_URL ?? '').trim();
  const origins: string[] = [];
  if (appUrl) origins.push(appUrl);
  if (process.env.NODE_ENV !== 'production') {
    origins.push('http://localhost:3000', 'http://localhost:5173');
  }
  return origins;
}

/**
 * Origin allowlist 기반 CSRF 방어.
 * GET/HEAD는 항상 통과.
 * POST/PUT/PATCH/DELETE는 Origin이 allowlist에 있어야 통과.
 */
export function verifyCsrfOrigin(req: NextRequest): boolean {
  if (!STATE_CHANGING.has(req.method)) return true;
  const origin = req.headers.get('origin') ?? '';
  if (!origin) return false;
  return getAllowedOrigins().includes(origin);
}
```

**Step 4: 테스트 실행 — 통과 확인**
```bash
cd web_saas && npx jest src/lib/__tests__/csrf.test.ts --no-coverage
```
기대: PASS (5/5)

**Step 5: 커밋**
```bash
cd web_saas && git add src/lib/csrf.ts src/lib/__tests__/csrf.test.ts
git commit -m "feat(security): add CSRF origin allowlist verification (A-4)"
```

---

### Task 8: middleware.ts — 라우트 보호 + CSRF

**Files:**
- Create: `web_saas/src/middleware.ts`

**Step 1: middleware.ts 구현**

```typescript
// web_saas/src/middleware.ts
import { auth } from '@/auth';
import { NextResponse } from 'next/server';
import { verifyCsrfOrigin } from '@/lib/csrf';

export default auth((req) => {
  // 1. 인증 확인 — 세션 없으면 401
  if (!req.auth) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  // 2. CSRF — 상태 변경 메서드에 Origin allowlist 검증
  if (!verifyCsrfOrigin(req)) {
    return NextResponse.json({ error: 'csrf_origin_mismatch' }, { status: 403 });
  }

  return NextResponse.next();
});

export const config = {
  // /api/webhooks/*, /api/internal/*, /api/auth/* 제외하고 모든 /api/* 보호
  matcher: ['/api/((?!webhooks|internal|auth).*)'],
};
```

**Step 2: 타입 확인**
```bash
cd web_saas && npx tsc --noEmit 2>&1 | head -30
```

**Step 3: 커밋**
```bash
cd web_saas && git add src/middleware.ts
git commit -m "feat(security): add NextAuth middleware + CSRF protection for /api/* (A-1, A-2, A-4)"
```

---

### Task 9: IDOR 제거 — 모든 사용자 API에서 organizationId 세션 주입

**Files:**
- Modify: `web_saas/src/app/api/evaluate/batch/route.ts`
- Modify: `web_saas/src/app/api/export/evaluations/route.ts`
- Modify: `web_saas/src/app/api/proposals/route.ts`
- Modify: `web_saas/src/app/api/search/bids/route.ts`
- Modify: `web_saas/src/app/api/pre-bid-signals/route.ts`

**Step 1: evaluate/batch — organizationId 세션에서 주입**

```typescript
// web_saas/src/app/api/evaluate/batch/route.ts
// 상단 import에 추가:
import { auth } from '@/auth';

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session?.user?.organizationId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const orgId = session.user.organizationId;

  // body에서는 organizationId 제거 — bidNoticeIds만 받음
  const { bidNoticeIds } = await req.json() as { bidNoticeIds: string[] };

  if (!bidNoticeIds?.length || bidNoticeIds.length > 50) {
    return NextResponse.json({ error: 'bidNoticeIds: 1–50 items required' }, { status: 400 });
  }

  // organizationId → orgId (세션값)으로 교체
  const org = await prisma.organization.findUnique({ where: { id: orgId } });
  if (!org) return NextResponse.json({ error: 'Organization not found' }, { status: 404 });

  const jobs = await Promise.all(
    bidNoticeIds.map((bidNoticeId) =>
      prisma.evaluationJob.upsert({
        where: { idempotencyKey: `batch_${orgId}_${bidNoticeId}` },
        create: {
          id: createId(),
          organizationId: orgId,
          bidNoticeId,
          idempotencyKey: `batch_${orgId}_${bidNoticeId}`,
          noticeRevision: 'batch',
          evaluationReason: 'user_requested',
        },
        update: {},
      })
    )
  );

  return NextResponse.json({ jobsCreated: jobs.length, jobs });
}
```

**Step 2: export/evaluations — 세션 주입**

```typescript
// web_saas/src/app/api/export/evaluations/route.ts
import { auth } from '@/auth';

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.user?.organizationId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const orgId = session.user.organizationId;

  // searchParams의 organizationId 제거 → orgId 사용
  const jobs = await prisma.evaluationJob.findMany({
    where: { organizationId: orgId },
    // ... 이하 동일
  });
  // ...
}
```

**Step 3: proposals — 세션 주입**

```typescript
// web_saas/src/app/api/proposals/route.ts
import { auth } from '@/auth';

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session?.user?.organizationId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const orgId = session.user.organizationId;

  const { bidNoticeId } = await req.json() as { bidNoticeId: string };
  // organizationId → orgId (세션값)
  // ... 이하 orgId 사용
}
```

**Step 4: search/bids — 공개 검색이지만 org 스코프 확인**

`search/bids`는 공개 공고 검색이므로 세션 없이도 조회 가능하게 유지. middleware matcher에서 이미 보호됨.

**Step 5: pre-bid-signals — 세션 연결 (공개 데이터이지만 authenticated user only)**

middleware가 `/api/pre-bid-signals`를 보호하므로 추가 변경 불필요.

**Step 6: 전체 빌드 확인**
```bash
cd web_saas && npx tsc --noEmit 2>&1 | head -30
```

**Step 7: 전체 테스트**
```bash
cd web_saas && npx jest --no-coverage
```
기대: 전체 PASS

**Step 8: 커밋**
```bash
cd web_saas && git add src/app/api/evaluate/ src/app/api/export/ src/app/api/proposals/
git commit -m "feat(security): remove IDOR — inject organizationId from session in all user APIs (A-3)"
```

---

## Wave 4 (D): 트랜잭션 강화

### Task 10: process-evaluation-job 상태 전이 트랜잭션 묶기

**Files:**
- Modify: `web_saas/src/app/api/internal/process-evaluation-job/route.ts`

**Step 1: handleScoreError 트랜잭션 적용**

현재: `findUnique` + `update` 2번 호출 (비원자)
변경: `prisma.$transaction`으로 묶기

```typescript
async function handleScoreError(jobId: string) {
  await prisma.$transaction(async (tx) => {
    const job = await tx.evaluationJob.findUnique({
      where: { id: jobId },
      select: { retryCount: true },
    });
    const n = (job?.retryCount ?? 0) + 1;
    if (n > MAX_RETRIES) {
      await tx.evaluationJob.update({
        where: { id: jobId },
        data: { status: 'RETRY_EXHAUSTED', retryCount: n, lockedAt: null, lockOwner: null },
      });
    } else {
      await tx.evaluationJob.update({
        where: { id: jobId },
        data: {
          status: 'SCORE_ERROR',
          retryCount: n,
          nextRetryAt: new Date(Date.now() + backoffMs(n)),
          lockedAt: null,
          lockOwner: null,
        },
      });
    }
  }).catch(() => {
    // best-effort: lock 해제 시도
    return prisma.evaluationJob.update({
      where: { id: jobId },
      data: { lockedAt: null, lockOwner: null },
    }).catch(() => {});
  });

  return NextResponse.json({ ok: false, reason: 'score_error' });
}
```

**Step 2: handleNotifyError 동일하게 적용 (패턴 동일)**

```typescript
async function handleNotifyError(jobId: string) {
  await prisma.$transaction(async (tx) => {
    const job = await tx.evaluationJob.findUnique({
      where: { id: jobId },
      select: { retryCount: true },
    });
    const n = (job?.retryCount ?? 0) + 1;
    if (n > MAX_RETRIES) {
      await tx.evaluationJob.update({
        where: { id: jobId },
        data: { status: 'RETRY_EXHAUSTED', retryCount: n, lockedAt: null, lockOwner: null },
      });
    } else {
      await tx.evaluationJob.update({
        where: { id: jobId },
        data: {
          status: 'NOTIFY_ERROR',
          retryCount: n,
          nextRetryAt: new Date(Date.now() + backoffMs(n)),
          lockedAt: null,
          lockOwner: null,
        },
      });
    }
  }).catch(() => {
    return prisma.evaluationJob.update({
      where: { id: jobId },
      data: { lockedAt: null, lockOwner: null },
    }).catch(() => {});
  });

  return NextResponse.json({ ok: false, reason: 'notify_error' });
}
```

**Step 3: 전체 테스트**
```bash
cd web_saas && npx jest --no-coverage
```
기대: PASS

**Step 4: 커밋**
```bash
cd web_saas && git add src/app/api/internal/process-evaluation-job/route.ts
git commit -m "feat(security): wrap evaluation job state transitions in transactions (D)"
```

---

## Wave 5 (E): 보안 회귀 테스트

### Task 11: 핵심 보안 유닛 테스트 모음

**Files:**
- Create: `web_saas/src/lib/__tests__/security-regression.test.ts`

**Step 1: 테스트 작성**

```typescript
// web_saas/src/lib/__tests__/security-regression.test.ts
/**
 * 보안 회귀 테스트 (Security Regression Tests)
 * 이 파일을 통과하면 기본 보안 요구사항이 충족된 것으로 간주.
 */

// --- env.ts: 부팅 검증 ---
describe('env.ts 부팅 검증', () => {
  let _resetEnv: () => void;
  let getEnv: () => unknown;

  beforeAll(async () => {
    ({ getEnv, _resetEnv } = await import('../env'));
  });

  it('필수 환경변수 누락 시 throw', () => {
    _resetEnv();
    const saved = { ...process.env };
    ['DATABASE_URL', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET',
     'WEBHOOK_SECRET', 'INTERNAL_API_SECRET', 'NEXTAUTH_SECRET', 'NEXTAUTH_URL']
      .forEach((k) => delete process.env[k]);
    expect(() => getEnv()).toThrow('startup validation failed');
    Object.assign(process.env, saved);
    _resetEnv();
  });
});

// --- safe-fetch.ts: SSRF ---
describe('safe-fetch: SSRF 방어', () => {
  let safeFetch: (url: string, domains: string[]) => Promise<Response>;

  beforeAll(async () => {
    jest.mock('dns', () => ({ promises: { lookup: jest.fn() } }));
    ({ safeFetch } = await import('../safe-fetch'));
  });

  it('http 스킴 거부', async () => {
    await expect(safeFetch('http://www.g2b.go.kr/f.hwp', ['.go.kr'])).rejects.toThrow('only https');
  });

  it('allowlist 외 도메인 거부', async () => {
    const dns = jest.requireMock('dns');
    dns.promises.lookup.mockResolvedValue({ address: '1.2.3.4', family: 4 });
    await expect(safeFetch('https://evil.com/f.hwp', ['.go.kr'])).rejects.toThrow('not in allowlist');
  });

  it('AWS metadata IP 거부', async () => {
    const dns = jest.requireMock('dns');
    dns.promises.lookup.mockResolvedValue({ address: '169.254.169.254', family: 4 });
    await expect(safeFetch('https://www.g2b.go.kr/f.hwp', ['.go.kr'])).rejects.toThrow('private IP');
  });
});

// --- csrf.ts: Origin 검증 ---
describe('csrf.ts: Origin allowlist', () => {
  let verifyCsrfOrigin: (req: import('next/server').NextRequest) => boolean;
  const APP = 'https://app.kirabot.kr';

  beforeAll(async () => {
    process.env.NEXT_PUBLIC_APP_URL = APP;
    ({ verifyCsrfOrigin } = await import('../csrf'));
  });

  it('GET은 항상 통과', () => {
    const { NextRequest } = jest.requireActual('next/server');
    const req = new NextRequest('http://localhost/api/x', {
      method: 'GET',
      headers: { origin: 'https://evil.com' },
    });
    expect(verifyCsrfOrigin(req)).toBe(true);
  });

  it('POST + 다른 origin 거부', () => {
    const { NextRequest } = jest.requireActual('next/server');
    const req = new NextRequest('http://localhost/api/x', {
      method: 'POST',
      headers: { origin: 'https://evil.com' },
    });
    expect(verifyCsrfOrigin(req)).toBe(false);
  });

  it('POST + 허용 origin 통과', () => {
    const { NextRequest } = jest.requireActual('next/server');
    const req = new NextRequest('http://localhost/api/x', {
      method: 'POST',
      headers: { origin: APP },
    });
    expect(verifyCsrfOrigin(req)).toBe(true);
  });
});

// --- internal-auth.ts: HMAC ---
describe('internal-auth.ts: HMAC 재전송 방지', () => {
  it('타임스탬프 범위 초과 시 401', async () => {
    const { verifyInternalAuth } = await import('../internal-auth');
    const { NextRequest } = jest.requireActual('next/server');
    const req = new NextRequest('http://localhost/api/internal/x', {
      method: 'POST',
      headers: {
        'x-internal-timestamp': '1000', // 2001년 — 범위 초과
        'x-internal-nonce': 'nonce1',
        'x-internal-signature': 'bad',
      },
    });
    const result = await verifyInternalAuth(req, '{}');
    expect(result?.status).toBe(401);
  });
});
```

**Step 2: 테스트 실행**
```bash
cd web_saas && npx jest src/lib/__tests__/security-regression.test.ts --no-coverage
```
기대: PASS

**Step 3: 전체 테스트 최종 확인**
```bash
cd web_saas && npx jest --no-coverage 2>&1 | tail -20
```
기대: 전체 PASS, 0 failures

**Step 4: 커밋**
```bash
cd web_saas && git add src/lib/__tests__/security-regression.test.ts
git commit -m "test(security): add security regression test suite (E)"
```

---

## 최종 확인

```bash
# 전체 테스트
cd web_saas && npx jest --no-coverage

# TypeScript 오류 없음 확인
cd web_saas && npx tsc --noEmit

# 커밋 목록 확인
git log --oneline -8
```

기대 커밋 목록:
```
feat(security): add CSRF origin allowlist...
feat(auth): add NextAuth v5...
feat(db): add User model...
feat(security): add HMAC auth for all /api/internal/*...
feat(security): add safeFetch SSRF defense...
feat(security): cap input limits, fix prisma log level...
feat(security): add zod env validation + fix stripe...
```

---

## 환경변수 추가 항목 (배포 전 .env에 설정 필요)

```
INTERNAL_API_SECRET=<최소 32자 랜덤 문자열>
NEXTAUTH_SECRET=<최소 32자 랜덤 문자열>
NEXTAUTH_URL=https://your-domain.com
NEXT_PUBLIC_APP_URL=https://your-domain.com
ATTACHMENT_ALLOWED_DOMAINS=.go.kr,.g2b.go.kr
```
