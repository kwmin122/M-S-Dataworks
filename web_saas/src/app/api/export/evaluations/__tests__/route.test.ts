import { NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';
import { GET } from '../route';

const mockAuth = jest.fn();
jest.mock('@/auth', () => ({
  auth: () => mockAuth(),
}));

jest.mock('@/lib/export/buildEvaluationExcel', () => ({
  buildEvaluationExcel: jest.fn().mockResolvedValue(new ArrayBuffer(8)),
}));

describe('GET /api/export/evaluations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns 401 when session organizationId is missing', async () => {
    mockAuth.mockResolvedValue(null);
    const req = new NextRequest(
      'http://localhost/api/export/evaluations?organizationId=org-victim',
      { method: 'GET' }
    );

    const res = await GET(req);
    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toEqual({ error: 'unauthorized' });
  });

  it('queries evaluation jobs with session organizationId only', async () => {
    mockAuth.mockResolvedValue({ user: { organizationId: 'org-session' } });
    (prisma.evaluationJob.findMany as jest.Mock).mockResolvedValue([]);

    const req = new NextRequest(
      'http://localhost/api/export/evaluations?organizationId=org-victim',
      { method: 'GET' }
    );

    const res = await GET(req);
    expect(res.status).toBe(200);
    expect(prisma.evaluationJob.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { organizationId: 'org-session' },
      })
    );
  });
});
