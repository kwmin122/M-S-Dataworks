import { NextRequest } from 'next/server';

const APP_URL = 'https://app.kirabot.kr';

jest.mock('@/lib/env', () => ({
  getEnv: jest.fn(() => ({
    NEXT_PUBLIC_APP_URL: APP_URL,
    NODE_ENV: 'test',
  })),
}));

import { verifyCsrfOrigin } from '../csrf';

function req(method: string, origin: string | null): NextRequest {
  const headers: Record<string, string> = {};
  if (origin !== null) headers.origin = origin;
  return new NextRequest('http://localhost/api/test', { method, headers });
}

describe('verifyCsrfOrigin', () => {
  it('allows GET regardless of origin', () => {
    expect(verifyCsrfOrigin(req('GET', 'https://evil.com'))).toBe(true);
    expect(verifyCsrfOrigin(req('GET', null))).toBe(true);
  });

  it('allows POST for allowlisted app origin', () => {
    expect(verifyCsrfOrigin(req('POST', APP_URL))).toBe(true);
  });

  it('blocks POST for non-allowlisted origin', () => {
    expect(verifyCsrfOrigin(req('POST', 'https://evil.com'))).toBe(false);
  });

  it('blocks POST without origin header', () => {
    expect(verifyCsrfOrigin(req('POST', null))).toBe(false);
  });

  it('allows DELETE for allowlisted app origin', () => {
    expect(verifyCsrfOrigin(req('DELETE', APP_URL))).toBe(true);
  });
});
