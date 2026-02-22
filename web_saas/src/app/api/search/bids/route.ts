import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { buildSearchConditions } from '@/lib/search/buildSearchQuery';
import type { Prisma } from '@prisma/client';

export async function POST(req: NextRequest) {
  const body = await req.json() as {
    keywords?: string[];
    region?: string;
    minAmt?: number;
    maxAmt?: number;
    excludeExpired?: boolean;
    limit?: number;
  };

  const where = buildSearchConditions({
    keywords: body.keywords,
    region: body.region,
    minAmt: body.minAmt,
    maxAmt: body.maxAmt,
    excludeExpired: body.excludeExpired,
  }) as Prisma.BidNoticeWhereInput;

  const notices = await prisma.bidNotice.findMany({
    where,
    orderBy: { publishedAt: 'desc' },
    take: body.limit ?? 50,
    select: {
      id: true,
      title: true,
      region: true,
      category: true,
      url: true,
      publishedAt: true,
      deadlineAt: true,
      source: true,
      externalId: true,
    },
  });

  return NextResponse.json({ notices, total: notices.length });
}
