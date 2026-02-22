import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createId } from '@/lib/ids';
import { isUniqueConstraintError } from '@/lib/errors';
import { verifyWebhookSignature } from '@/lib/hmac';
import { getEnv } from '@/lib/env';

const REPLAY_WINDOW_SEC = 300;

export async function verifyInternalAuth(
  req: NextRequest,
  rawBody: string
): Promise<NextResponse | null> {
  const ts = req.headers.get('x-internal-timestamp') ?? '';
  const nonce = req.headers.get('x-internal-nonce') ?? '';
  const signature = req.headers.get('x-internal-signature') ?? '';
  const { INTERNAL_API_SECRET: secret } = getEnv();

  const tsNum = parseInt(ts, 10);
  if (!tsNum || Math.abs(Date.now() / 1000 - tsNum) > REPLAY_WINDOW_SEC) {
    return NextResponse.json({ error: 'timestamp_out_of_range' }, { status: 401 });
  }

  const valid = verifyWebhookSignature({ ts, nonce, rawBody, signature, secret });
  if (!valid) {
    return NextResponse.json({ error: 'invalid_signature' }, { status: 401 });
  }

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

  return null;
}
