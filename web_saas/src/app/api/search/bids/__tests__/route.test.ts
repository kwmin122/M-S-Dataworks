import { NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';
import { POST } from '../route';

describe('POST /api/search/bids', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('caps limit to 100 for basic filter path', async () => {
    (prisma.bidNotice.findMany as jest.Mock).mockResolvedValue([]);

    const req = new NextRequest('http://localhost/api/search/bids', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ limit: 1_000_000 }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(prisma.bidNotice.findMany).toHaveBeenCalledWith(
      expect.objectContaining({ take: 100 })
    );
  });

  it('clamps negative limit to minimum 1', async () => {
    (prisma.bidNotice.findMany as jest.Mock).mockResolvedValue([]);

    const req = new NextRequest('http://localhost/api/search/bids', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ limit: -10 }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(prisma.bidNotice.findMany).toHaveBeenCalledWith(
      expect.objectContaining({ take: 1 })
    );
  });

  it('caps limit to 100 for attachment FTS path too', async () => {
    (prisma.$queryRaw as jest.Mock).mockResolvedValue([]);

    const req = new NextRequest('http://localhost/api/search/bids', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        keywords: ['CCTV'],
        includeAttachmentText: true,
        limit: 999999,
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(prisma.$queryRaw).toHaveBeenCalledTimes(1);
    const call = (prisma.$queryRaw as jest.Mock).mock.calls[0];
    const firstArg = call[0] as { values?: unknown[] };
    const values =
      Array.isArray(firstArg?.values) ? firstArg.values : call.slice(1);
    expect(values).toContain(100);
  });
});
