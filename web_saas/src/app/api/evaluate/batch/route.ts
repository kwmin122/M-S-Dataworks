import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

export async function POST(req: NextRequest) {
  const { bidNoticeIds, organizationId } = await req.json() as {
    bidNoticeIds: string[];
    organizationId: string;
  };

  if (!bidNoticeIds?.length || bidNoticeIds.length > 50 || !organizationId) {
    return NextResponse.json(
      { error: 'bidNoticeIds: 1–50 items required' },
      { status: 400 }
    );
  }

  const org = await prisma.organization.findUnique({ where: { id: organizationId } });
  if (!org) return NextResponse.json({ error: 'Organization not found' }, { status: 404 });

  const jobs = await Promise.all(
    bidNoticeIds.map((bidNoticeId) =>
      prisma.evaluationJob.upsert({
        where: {
          idempotencyKey: `batch_${organizationId}_${bidNoticeId}`,
        },
        create: {
          id: createId(),
          organizationId,
          bidNoticeId,
          idempotencyKey: `batch_${organizationId}_${bidNoticeId}`,
          noticeRevision: 'batch',
          evaluationReason: 'user_requested',
        },
        update: {},
      })
    )
  );

  return NextResponse.json({ jobsCreated: jobs.length, jobs });
}
