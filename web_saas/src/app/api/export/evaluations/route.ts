import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { buildEvaluationExcel } from '@/lib/export/buildEvaluationExcel';
import { auth } from '@/auth';

export async function GET(req: NextRequest) {
  const session = await auth();
  const orgId = session?.user?.organizationId;
  if (!orgId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const jobs = await prisma.evaluationJob.findMany({
    where: { organizationId: orgId },
    include: { bidNotice: true },
    orderBy: { createdAt: 'desc' },
    take: 200,
  });

  const rows = jobs.map((j) => ({
    title: j.bidNotice.title,
    estimatedAmt: j.bidNotice.estimatedAmt,
    deadlineAt: j.bidNotice.deadlineAt,
    region: j.bidNotice.region,
    isEligible: j.isEligible,
    evaluationReason: j.evaluationReason,
    actionPlan: j.actionPlan,
    url: j.bidNotice.url,
  }));

  const bytes = await buildEvaluationExcel(rows);

  return new NextResponse(bytes, {
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'Content-Disposition': 'attachment; filename="kirabot_evaluations.xlsx"',
    },
  });
}
