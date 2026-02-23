import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';
import { auth } from '@/auth';

export async function POST(req: NextRequest) {
  const session = await auth();
  const orgId = session?.user?.organizationId;
  if (!orgId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const { bidNoticeIds } = await req.json() as {
    bidNoticeIds: string[];
  };

  if (!bidNoticeIds?.length || bidNoticeIds.length > 50) {
    return NextResponse.json(
      { error: 'bidNoticeIds: 1–50 items required' },
      { status: 400 }
    );
  }

  const org = await prisma.organization.findUnique({ where: { id: orgId } });
  if (!org) return NextResponse.json({ error: 'Organization not found' }, { status: 404 });

  const jobs = await Promise.all(
    bidNoticeIds.map((bidNoticeId) =>
      prisma.evaluationJob.upsert({
        where: {
          idempotencyKey: `batch_${orgId}_${bidNoticeId}`,
        },
        create: {
          id: createId(),
          organizationId: orgId,
          bidNoticeId,
          idempotencyKey: `batch_${orgId}_${bidNoticeId}`,
          noticeRevision: 'batch',
          evaluationReason: 'user_requested',
        },
        update: {},
      })
    )
  );

  return NextResponse.json({ jobsCreated: jobs.length, jobs });
}
