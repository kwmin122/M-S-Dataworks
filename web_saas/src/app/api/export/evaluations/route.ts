import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { buildEvaluationExcel } from '@/lib/export/buildEvaluationExcel';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const organizationId = searchParams.get('organizationId');
  if (!organizationId) {
    return NextResponse.json({ error: 'organizationId required' }, { status: 400 });
  }

  const jobs = await prisma.evaluationJob.findMany({
    where: { organizationId },
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

  const buffer = await buildEvaluationExcel(rows);

  return new NextResponse(buffer, {
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'Content-Disposition': 'attachment; filename="kirabot_evaluations.xlsx"',
    },
  });
}
