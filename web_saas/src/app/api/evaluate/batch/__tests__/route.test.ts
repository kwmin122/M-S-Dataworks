import { NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';
import { POST } from '../route';

describe('POST /api/evaluate/batch', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('rejects bidNoticeIds larger than 50', async () => {
    (prisma.organization.findUnique as jest.Mock).mockResolvedValue({ id: 'org-1' });
    (prisma.evaluationJob.upsert as jest.Mock).mockResolvedValue({ id: 'job-1' });
    const bidNoticeIds = Array.from({ length: 51 }, (_, i) => `notice-${i}`);

    const req = new NextRequest('http://localhost/api/evaluate/batch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bidNoticeIds, organizationId: 'org-1' }),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
    await expect(res.json()).resolves.toEqual({
      error: 'bidNoticeIds: 1–50 items required',
    });
  });
});
