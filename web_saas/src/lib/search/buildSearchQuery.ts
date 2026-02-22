interface SearchConditions {
  keywords?: string[];
  region?: string;
  minAmt?: number;
  maxAmt?: number;
  excludeExpired?: boolean;
}

export function buildSearchConditions(cond: SearchConditions): Record<string, unknown> {
  const where: Record<string, unknown> = {};

  if (cond.keywords?.length) {
    where.OR = cond.keywords.map((kw) => ({
      title: { contains: kw, mode: 'insensitive' },
    }));
  }

  if (cond.region) {
    where.region = { contains: cond.region, mode: 'insensitive' };
  }

  if (cond.minAmt != null || cond.maxAmt != null) {
    where.estimatedAmt = {
      ...(cond.minAmt != null ? { gte: BigInt(cond.minAmt) } : {}),
      ...(cond.maxAmt != null ? { lte: BigInt(cond.maxAmt) } : {}),
    };
  }

  if (cond.excludeExpired) {
    where.deadlineAt = { gt: new Date() };
  }

  return where;
}
