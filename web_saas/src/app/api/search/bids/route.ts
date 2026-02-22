import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { buildSearchConditions } from '@/lib/search/buildSearchQuery';
import { buildFtsQuery } from '@/lib/search/ftsSearch';
import type { Prisma } from '@prisma/client';

interface FtsRow {
  id: string;
  title: string;
  region: string | null;
  category: string | null;
  published_at: Date | null;
  deadline_at: Date | null;
  url: string | null;
  source: string;
  external_id: string;
}

export async function POST(req: NextRequest) {
  const body = await req.json() as {
    keywords?: string[];
    region?: string;
    minAmt?: number;
    maxAmt?: number;
    excludeExpired?: boolean;
    includeAttachmentText?: boolean;
    limit?: number;
  };
  const cappedLimit = Math.min(Number(body.limit ?? 50), 100);

  let notices;

  if (body.includeAttachmentText && body.keywords?.length) {
    // FTS 경로: attachment_tsv @@ plainto_tsquery
    const ftsQuery = buildFtsQuery(body.keywords);
    const raw = await prisma.$queryRaw<FtsRow[]>`
      SELECT id, title, region, category, published_at, deadline_at, url, source, external_id
      FROM bid_notices
      WHERE attachment_tsv @@ plainto_tsquery('simple', ${ftsQuery})
      ORDER BY published_at DESC NULLS LAST
      LIMIT ${cappedLimit}
    `;
    notices = raw.map((n) => ({
      id: n.id,
      title: n.title,
      region: n.region,
      category: n.category,
      publishedAt: n.published_at,
      deadlineAt: n.deadline_at,
      url: n.url,
      source: n.source,
      externalId: n.external_id,
    }));
  } else {
    // 기본 필터 경로
    const where = buildSearchConditions({
      keywords: body.keywords,
      region: body.region,
      minAmt: body.minAmt,
      maxAmt: body.maxAmt,
      excludeExpired: body.excludeExpired,
    }) as Prisma.BidNoticeWhereInput;

    notices = await prisma.bidNotice.findMany({
      where,
      orderBy: { publishedAt: 'desc' },
      take: cappedLimit,
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
  }

  return NextResponse.json({ notices, total: notices.length });
}
