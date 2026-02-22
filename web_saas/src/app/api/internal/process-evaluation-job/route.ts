import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { consumeQuotaIfNeeded, getCurrentPeriodStart } from '@/lib/quota/consumeQuota';
import { verifyInternalAuth } from '@/lib/internal-auth';
import { Resend } from 'resend';

const FASTAPI_URL = process.env.FASTAPI_URL ?? 'http://rag_engine:8001';
const MAX_RETRIES = 3;
const resend = new Resend(process.env.RESEND_API_KEY);

function backoffMs(n: number): number {
  return Math.min(60_000 * Math.pow(2, n - 1), 3_600_000);
}

export async function POST(req: NextRequest) {
  const rawBody = await req.text();

  const authError = await verifyInternalAuth(req, rawBody);
  if (authError) return authError;

  const { jobId, workerId } = JSON.parse(rawBody) as { jobId: string; workerId: string };

  // 1. 원자 락 획득
  const acquired = await prisma.$executeRaw`
    UPDATE evaluation_jobs
    SET locked_at = NOW(), lock_owner = ${workerId}
    WHERE id = ${jobId} AND locked_at IS NULL
  `;
  if (acquired === 0) return NextResponse.json({ ok: false, reason: 'lock_not_acquired' });

  const job = await prisma.evaluationJob.findUnique({
    where: { id: jobId },
    include: {
      bidNotice: { select: { attachmentText: true, title: true } },
      organization: { select: { companyFacts: true, name: true } },
    },
  });
  if (!job) return NextResponse.json({ ok: false, reason: 'not_found' }, { status: 404 });

  // SCORED / NOTIFY_ERROR → 이메일 재시도만
  if (job.status === 'SCORED' || job.status === 'NOTIFY_ERROR') {
    return await sendNotification(jobId);
  }

  // PENDING / SCORE_ERROR → 쿼터 확인 + FastAPI 호출
  const periodStart = getCurrentPeriodStart();
  const quotaResult = await consumeQuotaIfNeeded({
    orgId: job.organizationId,
    evaluationJobId: jobId,
    periodStart,
  });

  if (quotaResult === 'QUOTA_EXCEEDED') {
    await prisma.evaluationJob.update({
      where: { id: jobId },
      data: { status: 'QUOTA_EXCEEDED', lockedAt: null, lockOwner: null },
    });
    return NextResponse.json({ ok: false, reason: 'quota_exceeded' });
  }

  try {
    const resp = await fetch(`${FASTAPI_URL}/api/analyze-bid`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        organization_id: job.organizationId,
        bid_notice_id: job.bidNoticeId,
        company_facts: job.organization.companyFacts,
        attachment_text: job.bidNotice.attachmentText ?? '',
      }),
    });

    if (!resp.ok) throw new Error(`FastAPI ${resp.status}`);
    const result = await resp.json();

    await prisma.evaluationJob.update({
      where: { id: jobId },
      data: {
        status: 'SCORED',
        isEligible: result.is_eligible,
        details: result.details,
        actionPlan: result.action_plan,
        lockedAt: null,
        lockOwner: null,
      },
    });

    return await sendNotification(jobId);
  } catch (_e) {
    return await handleScoreError(jobId);
  }
}

async function sendNotification(jobId: string) {
  const job = await prisma.evaluationJob.findUnique({
    where: { id: jobId },
    include: {
      organization: { select: { name: true } },
      bidNotice: { select: { title: true } },
    },
  });
  if (!job) {
    // Release lock best-effort
    await prisma.evaluationJob.update({
      where: { id: jobId },
      data: { lockedAt: null, lockOwner: null },
    }).catch(() => {});
    return NextResponse.json({ ok: false, reason: 'job_not_found' });
  }

  try {
    await resend.emails.send({
      from: 'bid-platform@yourdomain.com',
      to: 'notify@example.com', // TODO: Organization에 email 필드 추가 후 교체
      subject: `[입찰분석] ${job.bidNotice.title} — ${job.isEligible ? '입찰 가능' : '조건 부족'}`,
      text: `입찰 가능 여부: ${job.isEligible ? 'YES' : 'NO'}\n\n액션 플랜: ${job.actionPlan ?? ''}`,
      headers: { 'Idempotency-Key': job.id },
    });

    await prisma.evaluationJob.update({
      where: { id: jobId },
      data: { status: 'NOTIFIED', lockedAt: null, lockOwner: null },
    });
    return NextResponse.json({ ok: true });
  } catch (_e) {
    return await handleNotifyError(jobId);
  }
}

async function handleScoreError(jobId: string) {
  try {
    const job = await prisma.evaluationJob.findUnique({
      where: { id: jobId },
      select: { retryCount: true },
    });
    const n = (job?.retryCount ?? 0) + 1;
    if (n > MAX_RETRIES) {
      await prisma.evaluationJob.update({
        where: { id: jobId },
        data: { status: 'RETRY_EXHAUSTED', retryCount: n, lockedAt: null, lockOwner: null },
      });
    } else {
      await prisma.evaluationJob.update({
        where: { id: jobId },
        data: { status: 'SCORE_ERROR', retryCount: n, nextRetryAt: new Date(Date.now() + backoffMs(n)), lockedAt: null, lockOwner: null },
      });
    }
  } catch (_dbErr) {
    await prisma.evaluationJob.update({
      where: { id: jobId },
      data: { lockedAt: null, lockOwner: null },
    }).catch(() => {});
  }
  return NextResponse.json({ ok: false, reason: 'score_error' });
}

async function handleNotifyError(jobId: string) {
  try {
    const job = await prisma.evaluationJob.findUnique({
      where: { id: jobId },
      select: { retryCount: true },
    });
    const n = (job?.retryCount ?? 0) + 1;
    if (n > MAX_RETRIES) {
      await prisma.evaluationJob.update({
        where: { id: jobId },
        data: { status: 'RETRY_EXHAUSTED', retryCount: n, lockedAt: null, lockOwner: null },
      });
    } else {
      await prisma.evaluationJob.update({
        where: { id: jobId },
        data: { status: 'NOTIFY_ERROR', retryCount: n, nextRetryAt: new Date(Date.now() + backoffMs(n)), lockedAt: null, lockOwner: null },
      });
    }
  } catch (_dbErr) {
    await prisma.evaluationJob.update({
      where: { id: jobId },
      data: { lockedAt: null, lockOwner: null },
    }).catch(() => {});
  }
  return NextResponse.json({ ok: false, reason: 'notify_error' });
}
