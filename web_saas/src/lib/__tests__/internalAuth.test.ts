import { createHmac } from 'crypto';
import { NextRequest } from 'next/server';
import { verifyInternalAuth } from '../internal-auth';
import { _resetEnv } from '../env';
import { prisma } from '@/lib/prisma';

const SECRET = 'a'.repeat(32);
const REQUIRED_ENV = {
  DATABASE_URL: 'postgresql://x',
  STRIPE_SECRET_KEY: 'sk_test_abc',
  STRIPE_WEBHOOK_SECRET: 'whsec_abc',
  WEBHOOK_SECRET: 'w'.repeat(32),
  INTERNAL_API_SECRET: SECRET,
  NEXTAUTH_SECRET: 'n'.repeat(32),
  NEXTAUTH_URL: 'http://localhost:3000',
  ATTACHMENT_ALLOWED_DOMAINS: '.go.kr',
  FASTAPI_URL: 'http://localhost:8001',
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
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
  _resetEnv();
});

beforeEach(() => {
  jest.clearAllMocks();
  _resetEnv();
});

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
  const signature =
    overrides.signature ??
    createHmac('sha256', SECRET).update(signingString).digest('hex');

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

describe('verifyInternalAuth', () => {
  it('returns null for valid signature', async () => {
    (prisma.usedNonce.create as jest.Mock).mockResolvedValue({});
    const req = makeRequest({});
    const result = await verifyInternalAuth(req, '{"jobId":"j1"}');
    expect(result).toBeNull();
  });

  it('returns 401 for old timestamp', async () => {
    const req = makeRequest({ ts: '1000' });
    const result = await verifyInternalAuth(req, '{"jobId":"j1"}');
    expect(result?.status).toBe(401);
  });

  it('returns 401 for invalid signature', async () => {
    const req = makeRequest({ signature: 'deadbeef'.repeat(8) });
    const result = await verifyInternalAuth(req, '{"jobId":"j1"}');
    expect(result?.status).toBe(401);
  });

  it('returns 409 when nonce is reused', async () => {
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
});
