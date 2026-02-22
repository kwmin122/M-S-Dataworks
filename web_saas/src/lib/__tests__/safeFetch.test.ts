import { safeFetch } from '../safe-fetch';

jest.mock('dns', () => ({
  promises: {
    lookup: jest.fn(),
  },
}));

import dns from 'dns';

const mockLookup = dns.promises.lookup as jest.Mock;
const ALLOWED = ['.go.kr'];

beforeEach(() => {
  jest.clearAllMocks();
});

it('rejects non-https scheme', async () => {
  await expect(
    safeFetch('http://www.g2b.go.kr/file.hwp', ALLOWED)
  ).rejects.toThrow('only https allowed');
});

it('rejects non-allowlisted hostname', async () => {
  mockLookup.mockResolvedValue({ address: '1.2.3.4', family: 4 });
  await expect(
    safeFetch('https://evil.com/file.hwp', ALLOWED)
  ).rejects.toThrow('not in allowlist');
});

it('rejects private loopback IP', async () => {
  mockLookup.mockResolvedValue([{ address: '127.0.0.1', family: 4 }]);
  await expect(
    safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED)
  ).rejects.toThrow('private IP');
});

it('rejects metadata/link-local IP', async () => {
  mockLookup.mockResolvedValue([{ address: '169.254.169.254', family: 4 }]);
  await expect(
    safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED)
  ).rejects.toThrow('private IP');
});

it('rejects private IPv6 addresses too', async () => {
  mockLookup.mockResolvedValue([{ address: 'fe80::1', family: 6 }]);
  await expect(
    safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED)
  ).rejects.toThrow('private IP');
});

it('allows public IP on allowlisted hostname', async () => {
  mockLookup.mockResolvedValue([{ address: '1.2.3.4', family: 4 }]);
  global.fetch = jest
    .fn()
    .mockResolvedValue(new Response(new Uint8Array([1, 2, 3]), { status: 200 })) as unknown as typeof fetch;

  const res = await safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED);
  expect(res.status).toBe(200);
  expect(global.fetch).toHaveBeenCalledWith(
    'https://www.g2b.go.kr/file.hwp',
    expect.objectContaining({ redirect: 'manual' })
  );
});

it('rejects redirects', async () => {
  mockLookup.mockResolvedValue([{ address: '1.2.3.4', family: 4 }]);
  global.fetch = jest
    .fn()
    .mockResolvedValue(new Response(null, { status: 301 })) as unknown as typeof fetch;

  await expect(
    safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED)
  ).rejects.toThrow('redirect blocked');
});

it('rejects DNS rebinding when pre/post lookup differs', async () => {
  mockLookup
    .mockResolvedValueOnce([{ address: '1.2.3.4', family: 4 }])
    .mockResolvedValueOnce([{ address: '1.2.3.5', family: 4 }]);
  global.fetch = jest
    .fn()
    .mockResolvedValue(new Response(new Uint8Array([1]), { status: 200 })) as unknown as typeof fetch;

  await expect(
    safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED)
  ).rejects.toThrow('DNS rebinding detected');
});

it('rejects DNS rebinding when post-lookup resolves to private IP', async () => {
  mockLookup
    .mockResolvedValueOnce([{ address: '1.2.3.4', family: 4 }])
    .mockResolvedValueOnce([{ address: '169.254.169.254', family: 4 }]);
  global.fetch = jest
    .fn()
    .mockResolvedValue(new Response(new Uint8Array([1]), { status: 200 })) as unknown as typeof fetch;

  await expect(
    safeFetch('https://www.g2b.go.kr/file.hwp', ALLOWED)
  ).rejects.toThrow('post-fetch resolved to private IP');
});
