import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { matchStrengths } from '@/lib/strengthCard/buildStrengthCard';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ bidNoticeId: string }> }
) {
  const { bidNoticeId } = await params;
  const { searchParams } = new URL(req.url);
  const organizationId = searchParams.get('organizationId');

  if (!organizationId) {
    return NextResponse.json({ error: 'organizationId required' }, { status: 400 });
  }

  const [notice, org] = await Promise.all([
    prisma.bidNotice.findUnique({ where: { id: bidNoticeId } }),
    prisma.organization.findUnique({ where: { id: organizationId } }),
  ]);

  if (!notice || !org) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const facts = org.companyFacts as Record<string, unknown>;

  const evalJob = await prisma.evaluationJob.findFirst({
    where: { organizationId, bidNoticeId },
    orderBy: { createdAt: 'desc' },
  });

  const requirements = (evalJob?.details as Record<string, unknown>) ?? {};
  const { strengths, gaps } = matchStrengths(
    facts as Parameters<typeof matchStrengths>[0],
    requirements as Parameters<typeof matchStrengths>[1],
  );

  return NextResponse.json({
    notice: { title: notice.title, region: notice.region, deadlineAt: notice.deadlineAt },
    strengths,
    gaps,
    isEligible: evalJob?.isEligible ?? null,
    actionPlan: evalJob?.actionPlan ?? null,
  });
}
