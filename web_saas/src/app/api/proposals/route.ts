import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';
import { auth } from '@/auth';
import { getEnv } from '@/lib/env';

export async function POST(req: NextRequest) {
  const session = await auth();
  const orgId = session?.user?.organizationId;
  if (!orgId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const { bidNoticeId } = await req.json() as {
    bidNoticeId: string;
  };

  if (!bidNoticeId) {
    return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
  }

  const [notice, org] = await Promise.all([
    prisma.bidNotice.findUnique({ where: { id: bidNoticeId } }),
    prisma.organization.findUnique({ where: { id: orgId } }),
  ]);

  if (!notice) return NextResponse.json({ error: 'BidNotice not found' }, { status: 404 });
  if (!org) return NextResponse.json({ error: 'Organization not found' }, { status: 404 });

  const { FASTAPI_URL: ragUrl } = getEnv();
  const ragRes = await fetch(`${ragUrl}/api/generate-proposal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      notice_text: `${notice.title} ${notice.attachmentText ?? ''}`.slice(0, 2000),
      company_info: org.companyFacts,
    }),
    signal: AbortSignal.timeout(30_000),
  });

  if (!ragRes.ok) {
    return NextResponse.json({ error: 'Proposal generation failed' }, { status: 502 });
  }

  const ragData = await ragRes.json() as { sections: Record<string, string>; status: string };

  const draft = await prisma.proposalDraft.create({
    data: {
      id: createId(),
      organizationId: orgId,
      bidNoticeId,
      status: 'DONE',
    },
  });

  return NextResponse.json({ draft, sections: ragData.sections });
}
