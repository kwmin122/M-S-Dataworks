import { NextRequest } from 'next/server';
import { verifyCsrfOrigin } from '../csrf';

const APP_URL = 'https://app.kirabot.kr';
const ORIGINAL_APP_URL = process.env.NEXT_PUBLIC_APP_URL;
const ORIGINAL_NODE_ENV = process.env.NODE_ENV;

beforeAll(() => {
  process.env.NEXT_PUBLIC_APP_URL = APP_URL;
  process.env.NODE_ENV = 'test';
});

afterAll(() => {
  if (ORIGINAL_APP_URL === undefined) delete process.env.NEXT_PUBLIC_APP_URL;
  else process.env.NEXT_PUBLIC_APP_URL = ORIGINAL_APP_URL;

  if (ORIGINAL_NODE_ENV === undefined) delete process.env.NODE_ENV;
  else process.env.NODE_ENV = ORIGINAL_NODE_ENV;
});

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
