import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { verifyInternalAuth } from '@/lib/internal-auth';

export async function GET(req: NextRequest) {
  const rawQuery = new URL(req.url).searchParams.toString();
  const authError = await verifyInternalAuth(req, rawQuery);
  if (authError) return authError;

  const { searchParams } = new URL(req.url);
  const organizationId = searchParams.get('organizationId');

  if (!organizationId) {
    return NextResponse.json({ error: 'organizationId required' }, { status: 400 });
  }

  const jobs = await prisma.evaluationJob.findMany({
    where: { organizationId },
    include: {
      bidNotice: {
        select: { title: true, region: true, deadlineAt: true, url: true },
      },
    },
    orderBy: { createdAt: 'desc' },
    take: 100,
  });

  return NextResponse.json({ jobs });
}
