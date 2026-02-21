import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createEvaluationJobsForBidNotice } from '@/lib/jobs/createEvaluationJobs';
import crypto from 'crypto';

const MAX_RETRIES = 3;

function backoffMs(retryCount: number): number {
  return Math.min(60_000 * Math.pow(2, retryCount - 1), 3_600_000);
}

export async function POST(req: NextRequest) {
  const { jobId, workerId } = await req.json();

  // 1. 원자 락 획득 (SELECT 후보 → UPDATE WHERE locked_at IS NULL)
  const acquired = await prisma.$executeRaw`
    UPDATE ingestion_jobs
    SET locked_at = NOW(), lock_owner = ${workerId}
    WHERE id = ${jobId}
      AND locked_at IS NULL
  `;
  if (acquired === 0) {
    return NextResponse.json({ ok: false, reason: 'lock_not_acquired' });
  }

  const job = await prisma.ingestionJob.findUnique({ where: { id: jobId } });
  if (!job) return NextResponse.json({ ok: false, reason: 'not_found' }, { status: 404 });

  try {
    // 2. 첨부파일 다운로드
    let fileBytes: Buffer;
    try {
      const resp = await fetch(job.attachmentUrl!);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      fileBytes = Buffer.from(await resp.arrayBuffer());
    } catch (e) {
      return await handleError(jobId, 'FETCH_ERROR', e);
    }

    // 3. contentHash 계산
    const contentHash = crypto.createHash('sha256').update(fileBytes).digest('hex');

    // 4. 텍스트 파싱 (HWP/PDF → plain text — 추후 파서 연동)
    let attachmentText: string;
    try {
      attachmentText = fileBytes.toString('utf8');
    } catch (e) {
      return await handleError(jobId, 'PARSE_ERROR', e);
    }

    // 5. BidNotice 업데이트 + IngestionJob COMPLETED (트랜잭션)
    await prisma.$transaction([
      prisma.bidNotice.update({
        where: { id: job.bidNoticeId },
        data: { attachmentText },
      }),
      prisma.ingestionJob.update({
        where: { id: jobId },
        data: { status: 'COMPLETED', contentHash, lockedAt: null, lockOwner: null },
      }),
    ]);

    // 6. EvaluationJob 생성 (interestConfig 필터 적용)
    const notice = await prisma.bidNotice.findUnique({
      where: { id: job.bidNoticeId },
      select: { title: true, category: true, region: true },
    });
    if (notice) {
      await createEvaluationJobsForBidNotice({
        bidNoticeId: job.bidNoticeId,
        noticeRevision: contentHash,
        noticeMeta: notice,
      });
    }

    return NextResponse.json({ ok: true });
  } catch (e) {
    return await handleError(jobId, 'FETCH_ERROR', e);
  }
}

async function handleError(
  jobId: string,
  errorStatus: 'FETCH_ERROR' | 'PARSE_ERROR',
  _err: unknown
) {
  try {
    const job = await prisma.ingestionJob.findUnique({
      where: { id: jobId },
      select: { retryCount: true },
    });
    const newRetryCount = (job?.retryCount ?? 0) + 1;

    if (newRetryCount > MAX_RETRIES) {
      await prisma.ingestionJob.update({
        where: { id: jobId },
        data: { status: 'RETRY_EXHAUSTED', retryCount: newRetryCount, lockedAt: null, lockOwner: null },
      });
    } else {
      const nextRetryAt = new Date(Date.now() + backoffMs(newRetryCount));
      await prisma.ingestionJob.update({
        where: { id: jobId },
        data: { status: errorStatus, retryCount: newRetryCount, nextRetryAt, lockedAt: null, lockOwner: null },
      });
    }
  } catch (_dbErr) {
    // Ensure lock is always released even if status update fails
    await prisma.ingestionJob.update({
      where: { id: jobId },
      data: { lockedAt: null, lockOwner: null },
    }).catch(() => {}); // Best-effort — stale_lock_reclaim will clean up if this also fails
  }

  return NextResponse.json({ ok: false, reason: errorStatus });
}
