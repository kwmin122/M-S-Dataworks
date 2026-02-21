import { buildSigningString, verifyWebhookSignature } from '../hmac';
import { createHmac } from 'crypto';

const SECRET = 'test_secret_32_chars_long_xxxxxx';

describe('buildSigningString', () => {
  it('should concatenate timestamp.nonce.body', () => {
    const result = buildSigningString('1700000000', 'my-nonce', '{"foo":1}');
    expect(result).toBe('1700000000.my-nonce.{"foo":1}');
  });
});

describe('verifyWebhookSignature', () => {
  it('should return true for valid signature', () => {
    const ts = '1700000000';
    const nonce = 'test-nonce';
    const body = '{"event":"test"}';
    const signingString = `${ts}.${nonce}.${body}`;
    const expected = createHmac('sha256', SECRET)
      .update(signingString)
      .digest('hex');
    expect(verifyWebhookSignature({ ts, nonce, rawBody: body, signature: expected, secret: SECRET })).toBe(true);
  });

  it('should return false for tampered nonce', () => {
    const ts = '1700000000';
    const body = '{"event":"test"}';
    const signingString = `${ts}.original-nonce.${body}`;
    const sig = createHmac('sha256', SECRET).update(signingString).digest('hex');
    expect(verifyWebhookSignature({ ts, nonce: 'tampered-nonce', rawBody: body, signature: sig, secret: SECRET })).toBe(false);
  });
});
