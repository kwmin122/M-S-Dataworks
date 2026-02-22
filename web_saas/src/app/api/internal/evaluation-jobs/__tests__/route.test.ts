import { createHmac } from 'crypto';
import { NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';
import { _resetEnv } from '@/lib/env';
import { GET } from '../route';

const SECRET = 'a'.repeat(32);
const REQUIRED_ENV = {
  DATABASE_URL: 'postgresql://x',
  STRIPE_SECRET_KEY: 'sk_test_abc',
  STRIPE_WEBHOOK_SECRET: 'whsec_abc',
  WEBHOOK_SECRET: 'w'.repeat(32),
  INTERNAL_API_SECRET: SECRET,
  NEXTAUTH_SECRET: 'n'.repeat(32),
  NEXTAUTH_URL: 'http://localhost:3000',
  FASTAPI_URL: 'http://localhost:8001',
  ATTACHMENT_ALLOWED_DOMAINS: '.go.kr',
  NODE_ENV: 'test',
} as const;

const ORIGINAL_ENV = Object.fromEntries(
  Object.keys(REQUIRED_ENV).map((k) => [k, process.env[k]])
) as Record<string, string | undefined>;

beforeAll(() => {
  Object.assign(process.env, REQUIRED_ENV);
  _resetEnv();
});

afterAll(() => {
  for (const [key, value] of Object.entries(ORIGINAL_ENV)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  _resetEnv();
});

beforeEach(() => {
  jest.clearAllMocks();
  _resetEnv();
});

function sign(ts: string, nonce: string, payload: string): string {
  return createHmac('sha256', SECRET).update(`${ts}.${nonce}.${payload}`).digest('hex');
}

describe('GET /api/internal/evaluation-jobs', () => {
  it('accepts request when signature payload includes querystring', async () => {
    const ts = String(Math.floor(Date.now() / 1000));
    const nonce = 'nonce-1';
    const query = 'organizationId=org-1';
    const signature = sign(ts, nonce, query);

    (prisma.usedNonce.create as jest.Mock).mockResolvedValue({});
    (prisma.evaluationJob.findMany as jest.Mock).mockResolvedValue([]);

    const req = new NextRequest(`http://localhost/api/internal/evaluation-jobs?${query}`, {
      method: 'GET',
      headers: {
        'x-internal-timestamp': ts,
        'x-internal-nonce': nonce,
        'x-internal-signature': signature,
      },
    });

    const res = await GET(req);
    expect(res.status).toBe(200);
    expect(prisma.evaluationJob.findMany).toHaveBeenCalledWith(
      expect.objectContaining({ where: { organizationId: 'org-1' } })
    );
  });
});
