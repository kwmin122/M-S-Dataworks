import { NextRequest } from 'next/server';

jest.mock('@/auth', () => ({
  auth: (
    handler: (
      req: NextRequest & { auth?: unknown },
      evt: unknown
    ) => Response | void | Promise<Response | void>
  ) => handler,
}));

const mockVerifyCsrfOrigin = jest.fn();
jest.mock('@/lib/csrf', () => ({
  verifyCsrfOrigin: (req: NextRequest) => mockVerifyCsrfOrigin(req),
}));

describe('middleware', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockVerifyCsrfOrigin.mockReturnValue(true);
  });

  it('returns 401 when session is missing', async () => {
    const { default: middleware } = await import('@/middleware');
    const req = { method: 'GET', auth: null } as unknown as NextRequest & { auth?: unknown };
    const middlewareAny = middleware as unknown as (req: unknown) => Promise<Response | void>;

    const res = await middlewareAny(req);
    expect(res).toBeInstanceOf(Response);
    const typedRes = res as Response;
    expect(typedRes.status).toBe(401);
    await expect(typedRes.json()).resolves.toEqual({ error: 'unauthorized' });
  });

  it('returns 403 when csrf origin check fails', async () => {
    const { default: middleware } = await import('@/middleware');
    mockVerifyCsrfOrigin.mockReturnValue(false);
    const req = {
      method: 'POST',
      auth: { user: { id: 'u1' } },
      headers: new Headers({ origin: 'https://evil.com' }),
    } as unknown as NextRequest & { auth?: unknown };
    const middlewareAny = middleware as unknown as (req: unknown) => Promise<Response | void>;

    const res = await middlewareAny(req);
    expect(res).toBeInstanceOf(Response);
    const typedRes = res as Response;
    expect(typedRes.status).toBe(403);
    await expect(typedRes.json()).resolves.toEqual({ error: 'csrf_origin_mismatch' });
  });

  it('passes through when authenticated and csrf check passes', async () => {
    const { default: middleware } = await import('@/middleware');
    const req = {
      method: 'POST',
      auth: { user: { id: 'u1' } },
      headers: new Headers({ origin: 'http://localhost:3000' }),
    } as unknown as NextRequest & { auth?: unknown };
    const middlewareAny = middleware as unknown as (req: unknown) => Promise<Response | void>;

    const res = await middlewareAny(req);
    expect(res).toBeInstanceOf(Response);
    expect((res as Response).status).toBe(200);
  });

  it('uses matcher excluding webhooks/internal/auth routes', async () => {
    const { config } = await import('@/middleware');
    expect(config.matcher).toEqual(['/api/((?!webhooks|internal|auth).*)']);
  });
});
