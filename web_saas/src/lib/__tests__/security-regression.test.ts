/**
 * 보안 회귀 테스트 (Security Regression)
 *
 * 이 파일이 모두 PASS = 설계 문서의 핵심 보안 요구사항 충족.
 * 새 기능 추가 시 이 파일을 먼저 확인하고, 회귀가 생기면 즉시 수정.
 *
 * Note: jest.mock은 파일 상단에서 한 번만 선언한다.
 *       proposals/__tests__/route.test.ts 패턴 참조:
 *         - auth: 래퍼 패턴 (mockAuthFn = jest.fn())
 *         - prisma: 직접 import 후 (prisma.xxx as jest.Mock) 캐스트
 */

import { NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma'; // moduleNameMapper → src/__mocks__/prisma.ts

// ── 전역 모킹 ──────────────────────────────────
const mockGetEnv = jest.fn();
jest.mock('@/lib/env', () => ({ getEnv: (...args: unknown[]) => mockGetEnv(...args) }));

jest.mock('dns', () => ({ promises: { lookup: jest.fn() } }));

// auth: 래퍼 패턴 — mockAuthFn을 직접 제어
const mockAuthFn = jest.fn();
jest.mock('@/auth', () => ({ auth: () => mockAuthFn() }));

// ──────────────────────────────────────────────
// Section 1: env.ts — 부팅 검증
// ──────────────────────────────────────────────
describe('env.ts: 부팅 시 필수 변수 검증', () => {
  it('필수 변수 누락 시 "startup validation failed" throw', () => {
    // jest.isolateModules + requireActual로 mock 우회 (resetModules 사용 금지)
    // resetModules는 describe-level mock 레퍼런스를 무효화시켜 하위 섹션에 부작용을 유발
    const saved = { ...process.env };
    ['DATABASE_URL', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET',
      'WEBHOOK_SECRET', 'INTERNAL_API_SECRET', 'NEXTAUTH_SECRET', 'NEXTAUTH_URL',
    ].forEach((k) => delete (process.env as Record<string, string | undefined>)[k]);

    jest.isolateModules(() => {
      const { getEnv: realGetEnv, _resetEnv } =
        jest.requireActual<typeof import('../env')>('../env');
      _resetEnv();
      expect(() => realGetEnv()).toThrow('startup validation failed');
    });

    Object.assign(process.env, saved);
  });
});

// ──────────────────────────────────────────────
// Section 2: safe-fetch.ts — SSRF 방어
// ──────────────────────────────────────────────
describe('safe-fetch: SSRF 방어', () => {
  let safeFetch: (url: string, domains: string[]) => Promise<Response>;
  let mockLookup: jest.Mock;

  beforeAll(async () => {
    const dns = await import('dns');
    mockLookup = dns.promises.lookup as jest.Mock;
    ({ safeFetch } = await import('../safe-fetch'));
  });

  beforeEach(() => jest.clearAllMocks());

  it('http 스킴 거부', async () => {
    await expect(safeFetch('http://www.g2b.go.kr/f.hwp', ['.go.kr']))
      .rejects.toThrow('only https allowed');
  });

  it('allowlist 외 도메인 거부', async () => {
    // allowlist 검사는 DNS 조회 이전에 수행되므로 mockLookup 설정 불필요
    mockLookup.mockResolvedValue([{ address: '1.2.3.4', family: 4 }]);
    await expect(safeFetch('https://evil.com/f.hwp', ['.go.kr']))
      .rejects.toThrow('not in allowlist');
  });

  it('AWS metadata IP (169.254.x) 거부', async () => {
    // dns.promises.lookup({ all: true }) → 배열 반환
    mockLookup.mockResolvedValue([{ address: '169.254.169.254', family: 4 }]);
    await expect(safeFetch('https://www.g2b.go.kr/f.hwp', ['.go.kr']))
      .rejects.toThrow('private IP');
  });

  it('loopback IP (127.0.0.1) 거부', async () => {
    mockLookup.mockResolvedValue([{ address: '127.0.0.1', family: 4 }]);
    await expect(safeFetch('https://www.g2b.go.kr/f.hwp', ['.go.kr']))
      .rejects.toThrow('private IP');
  });

  it('DNS rebinding — post-fetch IP가 사설 대역으로 변경 시 거부', async () => {
    mockLookup
      .mockResolvedValueOnce([{ address: '1.2.3.4', family: 4 }])       // pre-fetch
      .mockResolvedValueOnce([{ address: '169.254.169.254', family: 4 }]); // post-fetch
    global.fetch = jest.fn().mockResolvedValue(
      new Response(new Uint8Array([1]), { status: 200 })
    ) as unknown as typeof fetch;
    await expect(safeFetch('https://www.g2b.go.kr/f.hwp', ['.go.kr']))
      .rejects.toThrow(/private IP|DNS rebinding/);
  });

  it('3xx 리다이렉트 거부', async () => {
    mockLookup.mockResolvedValue([{ address: '1.2.3.4', family: 4 }]);
    global.fetch = jest.fn().mockResolvedValue(
      new Response(null, { status: 301 })
    ) as unknown as typeof fetch;
    await expect(safeFetch('https://www.g2b.go.kr/f.hwp', ['.go.kr']))
      .rejects.toThrow('redirect blocked');
  });
});

// ──────────────────────────────────────────────
// Section 3: csrf.ts — Origin allowlist
// ──────────────────────────────────────────────
describe('csrf.ts: Origin allowlist CSRF 방어 (프로덕션 설정)', () => {
  const APP = 'https://app.kirabot.kr';

  let verifyCsrfOrigin: (req: NextRequest) => boolean;

  beforeAll(async () => {
    mockGetEnv.mockReturnValue({ NEXT_PUBLIC_APP_URL: APP, NODE_ENV: 'production' });
    ({ verifyCsrfOrigin } = await import('../csrf'));
  });

  function makeReq(method: string, origin: string | null): NextRequest {
    const headers: Record<string, string> = {};
    if (origin !== null) headers.origin = origin;
    return new NextRequest('http://localhost/api/test', { method, headers });
  }

  it('GET은 origin 무관 통과', () => {
    expect(verifyCsrfOrigin(makeReq('GET', 'https://evil.com'))).toBe(true);
    expect(verifyCsrfOrigin(makeReq('GET', null))).toBe(true);
  });

  it('POST + 허용 origin 통과', () => {
    expect(verifyCsrfOrigin(makeReq('POST', APP))).toBe(true);
  });

  it('POST + 다른 origin 거부', () => {
    expect(verifyCsrfOrigin(makeReq('POST', 'https://evil.com'))).toBe(false);
  });

  it('POST + origin 헤더 없으면 거부', () => {
    expect(verifyCsrfOrigin(makeReq('POST', null))).toBe(false);
  });

  it('DELETE + 다른 origin 거부', () => {
    expect(verifyCsrfOrigin(makeReq('DELETE', 'https://evil.com'))).toBe(false);
  });
});

// ──────────────────────────────────────────────
// Section 4: internal-auth.ts — HMAC 재전송 방지
// ──────────────────────────────────────────────
describe('internal-auth.ts: HMAC 인증 + replay 방지', () => {
  let verifyInternalAuth: (req: NextRequest, rawBody: string) => Promise<Response | null>;

  beforeAll(async () => {
    mockGetEnv.mockReturnValue({ INTERNAL_API_SECRET: 'a'.repeat(32), NODE_ENV: 'test' });
    ({ verifyInternalAuth } = await import('../internal-auth'));
  });

  it('타임스탬프 범위 초과 시 401', async () => {
    const req = new NextRequest('http://localhost/api/internal/x', {
      method: 'POST',
      headers: {
        'x-internal-timestamp': '1000', // 2001년 — 범위 초과
        'x-internal-nonce': 'nonce1',
        'x-internal-signature': 'bad',
      },
    });
    const result = await verifyInternalAuth(req, '{}');
    expect((result as Response)?.status).toBe(401);
  });

  it('잘못된 서명 시 401', async () => {
    const ts = String(Math.floor(Date.now() / 1000));
    const req = new NextRequest('http://localhost/api/internal/x', {
      method: 'POST',
      headers: {
        'x-internal-timestamp': ts,
        'x-internal-nonce': 'nonce-bad-sig',
        'x-internal-signature': 'deadbeef'.repeat(8),
      },
    });
    const result = await verifyInternalAuth(req, '{}');
    expect((result as Response)?.status).toBe(401);
  });
});

// ──────────────────────────────────────────────
// Section 5: search/bids — limit 상한 100
// ──────────────────────────────────────────────
describe('POST /api/search/bids: limit 상한 100 강제', () => {
  // prisma는 moduleNameMapper로 src/__mocks__/prisma.ts에 자동 매핑됨
  // jest.requireMock 대신 직접 import를 사용해 동일 인스턴스 보장

  beforeEach(() => jest.clearAllMocks());

  it('limit=1000000 → take=100 으로 clamp', async () => {
    (prisma.bidNotice.findMany as jest.Mock).mockResolvedValue([]);
    const { POST } = await import('../../app/api/search/bids/route');

    const req = new NextRequest('http://localhost/api/search/bids', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ limit: 1_000_000 }),
    });
    await POST(req);

    expect(prisma.bidNotice.findMany as jest.Mock).toHaveBeenCalledWith(
      expect.objectContaining({ take: 100 })
    );
  });

  it('limit 미지정 → take=50 (기본값)', async () => {
    (prisma.bidNotice.findMany as jest.Mock).mockResolvedValue([]);
    const { POST } = await import('../../app/api/search/bids/route');

    const req = new NextRequest('http://localhost/api/search/bids', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({}),
    });
    await POST(req);

    expect(prisma.bidNotice.findMany as jest.Mock).toHaveBeenCalledWith(
      expect.objectContaining({ take: 50 })
    );
  });
});

// ──────────────────────────────────────────────
// Section 6: evaluate/batch — 배열 크기 제한 + IDOR 방어
// ──────────────────────────────────────────────
describe('POST /api/evaluate/batch: DoS 제한 + IDOR 방어', () => {
  // auth: 래퍼 패턴으로 mockAuthFn을 직접 제어
  // prisma: 직접 import로 동일 인스턴스 보장

  beforeEach(() => jest.clearAllMocks());

  it('세션 없는 요청 → 401', async () => {
    mockAuthFn.mockResolvedValue(null);
    const { POST } = await import('../../app/api/evaluate/batch/route');

    const req = new NextRequest('http://localhost/api/evaluate/batch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bidNoticeIds: ['n1'], organizationId: 'org-victim' }),
    });
    const res = await POST(req);
    expect(res.status).toBe(401);
  });

  it('bidNoticeIds 51개 → 400', async () => {
    mockAuthFn.mockResolvedValue({ user: { organizationId: 'org-1' } });
    const { POST } = await import('../../app/api/evaluate/batch/route');

    const req = new NextRequest('http://localhost/api/evaluate/batch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bidNoticeIds: Array.from({ length: 51 }, (_, i) => `n-${i}`) }),
    });
    const res = await POST(req);
    expect(res.status).toBe(400);
  });

  it('body의 organizationId 무시 — 세션 orgId만 사용', async () => {
    mockAuthFn.mockResolvedValue({ user: { organizationId: 'org-session' } });
    (prisma.organization.findUnique as jest.Mock).mockResolvedValue({ id: 'org-session' });
    (prisma.evaluationJob.upsert as jest.Mock).mockResolvedValue({ id: 'job-1' });
    const { POST } = await import('../../app/api/evaluate/batch/route');

    const req = new NextRequest('http://localhost/api/evaluate/batch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bidNoticeIds: ['n1'], organizationId: 'org-victim' }),
    });
    await POST(req);

    expect(prisma.organization.findUnique as jest.Mock).toHaveBeenCalledWith(
      expect.objectContaining({ where: { id: 'org-session' } })
    );
    expect(prisma.evaluationJob.upsert as jest.Mock).toHaveBeenCalledWith(
      expect.objectContaining({
        create: expect.objectContaining({ organizationId: 'org-session' }),
      })
    );
  });
});
