import { NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';
import { POST } from '../route';

const mockAuth = jest.fn();
jest.mock('@/auth', () => ({
  auth: () => mockAuth(),
}));

jest.mock('@/lib/env', () => ({
  getEnv: jest.fn(() => ({ FASTAPI_URL: 'http://localhost:8001' })),
}));

describe('POST /api/proposals', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({ sections: {}, status: 'ok' }),
    } as unknown as Response);
  });

  it('returns 401 when session organizationId is missing', async () => {
    mockAuth.mockResolvedValue(null);
    const req = new NextRequest('http://localhost/api/proposals', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bidNoticeId: 'notice-1', organizationId: 'org-victim' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toEqual({ error: 'unauthorized' });
  });

  it('uses session organizationId even when request body has another organizationId', async () => {
    mockAuth.mockResolvedValue({ user: { organizationId: 'org-session' } });
    (prisma.bidNotice.findUnique as jest.Mock).mockResolvedValue({
      id: 'notice-1',
      title: 'T',
      attachmentText: 'A',
    });
    (prisma.organization.findUnique as jest.Mock).mockResolvedValue({
      id: 'org-session',
      companyFacts: null,
    });
    (prisma.proposalDraft.create as jest.Mock).mockResolvedValue({ id: 'draft-1' });

    const req = new NextRequest('http://localhost/api/proposals', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bidNoticeId: 'notice-1', organizationId: 'org-victim' }),
    });

    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(prisma.organization.findUnique).toHaveBeenCalledWith({
      where: { id: 'org-session' },
    });
    expect(prisma.proposalDraft.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          organizationId: 'org-session',
        }),
      })
    );
  });
});
