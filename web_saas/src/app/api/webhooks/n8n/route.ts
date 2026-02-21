import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';
import { verifyWebhookSignature } from '@/lib/hmac';
import { isUniqueConstraintError } from '@/lib/errors';

const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET!;
const REPLAY_WINDOW_SEC = 300; // ±5분

export async function POST(req: NextRequest) {
  const rawBody = await req.text();
  const ts        = req.headers.get('x-timestamp') ?? '';
  const nonce     = req.headers.get('x-nonce') ?? '';
  const signature = req.headers.get('x-signature') ?? '';

  // 1. Timestamp 범위 검증
  const tsNum = parseInt(ts, 10);
  if (!tsNum || Math.abs(Date.now() / 1000 - tsNum) > REPLAY_WINDOW_SEC) {
    return NextResponse.json({ error: 'timestamp_out_of_range' }, { status: 401 });
  }

  // 2. 서명 검증 (nonce 포함 — nonce 교체 공격 방지)
  const valid = verifyWebhookSignature({ ts, nonce, rawBody, signature, secret: WEBHOOK_SECRET });
  if (!valid) {
    return NextResponse.json({ error: 'invalid_signature' }, { status: 401 });
  }

  // 3. Nonce 중복 방지 (create-only + P2002 catch)
  try {
    await prisma.usedNonce.create({
      data: { id: createId(), nonce, expiredAt: new Date((tsNum + 10 * 60) * 1000) },
    });
  } catch (e) {
    if (isUniqueConstraintError(e)) {
      return NextResponse.json({ error: 'replay_detected' }, { status: 409 });
    }
    throw e;
  }

  // 4. 이벤트 디스패치
  const payload = JSON.parse(rawBody) as { event: string; data: unknown };
  await dispatchEvent(payload.event, payload.data);

  return NextResponse.json({ ok: true });
}

async function dispatchEvent(event: string, data: unknown) {
  switch (event) {
    case 'ingestion.completed':
      await handleIngestionCompleted(data as IngestionCompletedPayload);
      break;
    case 'evaluation.process':
      await handleEvaluationProcess(data as EvaluationProcessPayload);
      break;
    default:
      console.warn(`[webhook] unknown event: ${event}`);
  }
}

interface IngestionCompletedPayload {
  ingestionJobId: string;
  bidNoticeId: string;
  contentHash: string;
}

interface EvaluationProcessPayload {
  jobId: string;
  workerId: string;
}

async function handleIngestionCompleted(_payload: IngestionCompletedPayload) {
  // Task 8에서 구현: createEvaluationJobsForBidNotice 호출
}

async function handleEvaluationProcess(_payload: EvaluationProcessPayload) {
  // Task 15에서 구현: process-evaluation-job 로직 호출
}
