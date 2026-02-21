import { createHmac, timingSafeEqual } from 'crypto';

export function buildSigningString(ts: string, nonce: string, rawBody: string): string {
  return `${ts}.${nonce}.${rawBody}`;
}

interface VerifyOptions {
  ts: string;
  nonce: string;
  rawBody: string;
  signature: string;
  secret: string;
}

export function verifyWebhookSignature({ ts, nonce, rawBody, signature, secret }: VerifyOptions): boolean {
  const signingString = buildSigningString(ts, nonce, rawBody);
  const expected = createHmac('sha256', secret).update(signingString).digest('hex');
  try {
    return timingSafeEqual(Buffer.from(expected, 'hex'), Buffer.from(signature, 'hex'));
  } catch {
    return false;
  }
}
