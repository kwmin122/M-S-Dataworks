import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

export const FREE_PLAN_LIMIT = 10;

export function getMaxCountForPlan(plan: string | null): number {
  return plan === 'PRO' ? -1 : FREE_PLAN_LIMIT;
}

export async function consumeQuotaIfNeeded(params: {
  orgId: string;
  evaluationJobId: string;
  periodStart: Date;
}): Promise<'OK' | 'QUOTA_EXCEEDED'> {
  const { orgId, evaluationJobId, periodStart } = params;

  return await prisma.$transaction(async (tx) => {
    const job = await tx.evaluationJob.findUnique({
      where: { id: evaluationJobId },
      select: { quotaConsumed: true },
    });
    if (job?.quotaConsumed) return 'OK';

    const sub = await tx.subscription.findUnique({
      where: { organizationId: orgId },
      select: { plan: true },
    });
    const maxCount = getMaxCountForPlan(sub?.plan ?? null);

    await tx.usageQuota.upsert({
      where: { organizationId_periodStart: { organizationId: orgId, periodStart } },
      create: { id: createId(), organizationId: orgId, periodStart, usedCount: 0, maxCount },
      update: {},
    });

    if (maxCount === -1) {
      await tx.evaluationJob.update({ where: { id: evaluationJobId }, data: { quotaConsumed: true } });
      return 'OK';
    }

    const affected = await tx.$executeRaw`
      UPDATE usage_quotas
      SET used_count = used_count + 1, updated_at = NOW()
      WHERE organization_id = ${orgId}
        AND period_start = ${periodStart}
        AND used_count < max_count
    `;
    if (affected === 0) return 'QUOTA_EXCEEDED';

    await tx.evaluationJob.update({ where: { id: evaluationJobId }, data: { quotaConsumed: true } });
    return 'OK';
  });
}

/** 현재 구독 주기의 periodStart(월 첫날 UTC)를 반환 */
export function getCurrentPeriodStart(): Date {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
}
