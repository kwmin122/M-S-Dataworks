import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

interface InterestConfig {
  keywords: string[];
  regions: string[];
}

interface NoticeMeta {
  title: string;
  category?: string | null;
  region?: string | null;
}

export function matchesInterestConfig(config: InterestConfig | null, notice: NoticeMeta): boolean {
  if (!config?.keywords?.length) return false;

  const keywordMatch = config.keywords.some(
    kw => notice.title.includes(kw) || (notice.category ?? '').includes(kw)
  );
  const regionMatch =
    !config.regions?.length || config.regions.includes(notice.region ?? '');

  return keywordMatch && regionMatch;
}

export async function createEvaluationJobsForBidNotice(params: {
  bidNoticeId: string;
  noticeRevision: string;
  noticeMeta: NoticeMeta;
}) {
  const { bidNoticeId, noticeRevision, noticeMeta } = params;

  const orgs = await prisma.organization.findMany({
    where: { subscription: { status: { in: ['ACTIVE', 'TRIALING'] } } },
    select: { id: true, interestConfig: true },
  });

  for (const org of orgs) {
    const config = org.interestConfig as InterestConfig | null;
    if (!matchesInterestConfig(config, noticeMeta)) continue;

    const idempotencyKey = `${org.id}:${bidNoticeId}:${noticeRevision}:auto`;
    await prisma.evaluationJob.upsert({
      where: { idempotencyKey },
      create: {
        id: createId(),
        organizationId: org.id,
        bidNoticeId,
        idempotencyKey,
        noticeRevision,
        evaluationReason: 'auto',
      },
      update: {},
    });
  }
}
