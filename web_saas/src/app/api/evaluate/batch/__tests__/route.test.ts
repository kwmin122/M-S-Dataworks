import { NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';
import { POST } from '../route';

const mockAuth = jest.fn();
jest.mock('@/auth', () => ({
  auth: () => mockAuth(),
}));

describe('POST /api/evaluate/batch', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns 401 when session organizationId is missing', async () => {
    mockAuth.mockResolvedValue(null);
    const req = new NextRequest('http://localhost/api/evaluate/batch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bidNoticeIds: ['notice-1'], organizationId: 'org-victim' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toEqual({ error: 'unauthorized' });
  });

  it('uses session organizationId even when request body has another organizationId', async () => {
    mockAuth.mockResolvedValue({ user: { organizationId: 'org-session' } });
    (prisma.organization.findUnique as jest.Mock).mockResolvedValue({ id: 'org-session' });
    (prisma.evaluationJob.upsert as jest.Mock).mockResolvedValue({ id: 'job-1' });

    const req = new NextRequest('http://localhost/api/evaluate/batch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bidNoticeIds: ['notice-1'], organizationId: 'org-victim' }),
    });

    await POST(req);

    expect(prisma.organization.findUnique).toHaveBeenCalledWith({
      where: { id: 'org-session' },
    });
    expect(prisma.evaluationJob.upsert).toHaveBeenCalledWith(
      expect.objectContaining({
        create: expect.objectContaining({
          organizationId: 'org-session',
        }),
      })
    );
  });

  it('rejects bidNoticeIds larger than 50', async () => {
    mockAuth.mockResolvedValue({ user: { organizationId: 'org-1' } });
    (prisma.organization.findUnique as jest.Mock).mockResolvedValue({ id: 'org-1' });
    (prisma.evaluationJob.upsert as jest.Mock).mockResolvedValue({ id: 'job-1' });
    const bidNoticeIds = Array.from({ length: 51 }, (_, i) => `notice-${i}`);

    const req = new NextRequest('http://localhost/api/evaluate/batch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bidNoticeIds }),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
    await expect(res.json()).resolves.toEqual({
      error: 'bidNoticeIds: 1–50 items required',
    });
  });
});
