import dns from 'dns';

const PRIVATE_RANGES: [number, number][] = [
  [0x7f000000, 0x7fffffff], // 127.0.0.0/8 loopback
  [0x0a000000, 0x0affffff], // 10.0.0.0/8
  [0xac100000, 0xac1fffff], // 172.16.0.0/12
  [0xc0a80000, 0xc0a8ffff], // 192.168.0.0/16
  [0xa9fe0000, 0xa9feffff], // 169.254.0.0/16
  [0xe0000000, 0xefffffff], // 224.0.0.0/4 multicast
  [0x00000000, 0x00ffffff], // 0.0.0.0/8
];

function ipv4ToInt(ip: string): number {
  return ip
    .split('.')
    .reduce((acc, part) => (acc << 8) + parseInt(part, 10), 0) >>> 0;
}

function isPrivateIp(ip: string): boolean {
  if (ip === '::1') return true;
  if (!ip.includes('.')) return false;
  const n = ipv4ToInt(ip);
  return PRIVATE_RANGES.some(([start, end]) => n >= start && n <= end);
}

async function readBodyWithinLimit(response: Response, maxBytes: number): Promise<Uint8Array> {
  if (!response.body) return new Uint8Array(0);

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!value) continue;
    total += value.byteLength;
    if (total > maxBytes) {
      await reader.cancel();
      throw new Error(`SSRF: response body exceeds ${maxBytes} bytes`);
    }
    chunks.push(value);
  }

  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return merged;
}

export async function safeFetch(
  url: string,
  allowedDomains: string[],
  maxBytes = 50 * 1024 * 1024
): Promise<Response> {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error('SSRF: invalid URL');
  }

  if (parsed.protocol !== 'https:') {
    throw new Error(`SSRF: only https allowed, got ${parsed.protocol}`);
  }

  const hostname = parsed.hostname.toLowerCase();
  const inAllowlist = allowedDomains.some((d) => {
    const domain = d.startsWith('.') ? d : `.${d}`;
    return hostname === d.replace(/^\./, '') || hostname.endsWith(domain);
  });
  if (!inAllowlist) {
    throw new Error(`SSRF: hostname ${hostname} not in allowlist`);
  }

  const preLookup = await dns.promises.lookup(hostname, { family: 4 });
  if (isPrivateIp(preLookup.address)) {
    throw new Error(`SSRF: resolved to private IP ${preLookup.address}`);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10_000);
  let response: Response;
  try {
    response = await fetch(url, {
      redirect: 'manual',
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }

  if (response.status >= 300 && response.status < 400) {
    throw new Error(`SSRF: redirect blocked (${response.status})`);
  }

  const contentLength = response.headers.get('content-length');
  if (contentLength && parseInt(contentLength, 10) > maxBytes) {
    throw new Error(`SSRF: content-length ${contentLength} exceeds ${maxBytes} bytes`);
  }

  // Re-resolve hostname after request and verify it did not rebind to private/internal.
  const postLookup = await dns.promises.lookup(hostname, { family: 4 });
  if (isPrivateIp(postLookup.address)) {
    throw new Error(`SSRF: post-fetch resolved to private IP ${postLookup.address}`);
  }
  if (postLookup.address !== preLookup.address) {
    throw new Error(
      `SSRF: DNS rebinding detected (${preLookup.address} -> ${postLookup.address})`
    );
  }

  const bodyBytes = await readBodyWithinLimit(response, maxBytes);
  return new Response(bodyBytes, {
    status: response.status,
    statusText: response.statusText,
    headers: new Headers(response.headers),
  });
}
