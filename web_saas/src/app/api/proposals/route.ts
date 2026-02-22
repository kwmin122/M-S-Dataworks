import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';

export async function POST(req: NextRequest) {
  const { organizationId, bidNoticeId } = await req.json() as {
    organizationId: string;
    bidNoticeId: string;
  };

  if (!organizationId || !bidNoticeId) {
    return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
  }

  const [notice, org] = await Promise.all([
    prisma.bidNotice.findUnique({ where: { id: bidNoticeId } }),
    prisma.organization.findUnique({ where: { id: organizationId } }),
  ]);

  if (!notice) return NextResponse.json({ error: 'BidNotice not found' }, { status: 404 });
  if (!org) return NextResponse.json({ error: 'Organization not found' }, { status: 404 });

  const ragUrl = process.env.FASTAPI_URL ?? 'http://localhost:8001';
  const ragRes = await fetch(`${ragUrl}/api/generate-proposal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      notice_text: `${notice.title} ${notice.attachmentText ?? ''}`.slice(0, 2000),
      company_info: org.companyFacts,
    }),
  });

  if (!ragRes.ok) {
    return NextResponse.json({ error: 'Proposal generation failed' }, { status: 502 });
  }

  const ragData = await ragRes.json() as { sections: Record<string, string>; status: string };

  const draft = await prisma.proposalDraft.create({
    data: {
      id: createId(),
      organizationId,
      bidNoticeId,
      status: 'DONE',
    },
  });

  return NextResponse.json({ draft, sections: ragData.sections });
}
