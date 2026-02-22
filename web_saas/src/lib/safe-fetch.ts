import dns from 'dns';
import net from 'net';

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

function isPrivateIpv4(ip: string): boolean {
  const n = ipv4ToInt(ip);
  return PRIVATE_RANGES.some(([start, end]) => n >= start && n <= end);
}

function stripZoneId(ip: string): string {
  const zoneIndex = ip.indexOf('%');
  return zoneIndex === -1 ? ip : ip.slice(0, zoneIndex);
}

function ipv6ToBigInt(ipv6: string): bigint {
  let value = stripZoneId(ipv6).toLowerCase();
  if (value.includes('.')) {
    const lastColon = value.lastIndexOf(':');
    if (lastColon === -1) throw new Error(`Invalid IPv6: ${ipv6}`);
    const ipv4Part = value.slice(lastColon + 1);
    const ipv4Int = ipv4ToInt(ipv4Part);
    const hi = ((ipv4Int >>> 16) & 0xffff).toString(16);
    const lo = (ipv4Int & 0xffff).toString(16);
    value = `${value.slice(0, lastColon)}:${hi}:${lo}`;
  }

  const halves = value.split('::');
  if (halves.length > 2) throw new Error(`Invalid IPv6: ${ipv6}`);

  const left = halves[0] ? halves[0].split(':').filter(Boolean) : [];
  const right = halves.length === 2 && halves[1] ? halves[1].split(':').filter(Boolean) : [];
  const hasCompression = halves.length === 2;
  const missing = 8 - (left.length + right.length);

  if (!hasCompression && left.length !== 8) throw new Error(`Invalid IPv6: ${ipv6}`);
  if (missing < 0) throw new Error(`Invalid IPv6: ${ipv6}`);

  const full = hasCompression
    ? [...left, ...Array(missing).fill('0'), ...right]
    : left;
  if (full.length !== 8) throw new Error(`Invalid IPv6: ${ipv6}`);

  let out = 0n;
  for (const seg of full) {
    if (!/^[0-9a-f]{1,4}$/i.test(seg)) {
      throw new Error(`Invalid IPv6 segment: ${seg}`);
    }
    out = (out << 16n) + BigInt(parseInt(seg, 16));
  }
  return out;
}

const IPV6_PRIVATE_RANGES: [bigint, bigint][] = [
  [0n, 0n], // ::/128 unspecified
  [1n, 1n], // ::1/128 loopback
  [ipv6ToBigInt('fc00::'), ipv6ToBigInt('fdff:ffff:ffff:ffff:ffff:ffff:ffff:ffff')], // fc00::/7
  [ipv6ToBigInt('fe80::'), ipv6ToBigInt('febf:ffff:ffff:ffff:ffff:ffff:ffff:ffff')], // fe80::/10
  [ipv6ToBigInt('ff00::'), ipv6ToBigInt('ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff')], // ff00::/8
];

function isPrivateIpv6(ipv6: string): boolean {
  const n = ipv6ToBigInt(ipv6);
  return IPV6_PRIVATE_RANGES.some(([start, end]) => n >= start && n <= end);
}

function isPrivateIp(ip: string): boolean {
  const normalized = stripZoneId(ip);
  if (normalized.startsWith('::ffff:')) {
    const mapped = normalized.slice(7);
    if (net.isIP(mapped) === 4) {
      return isPrivateIpv4(mapped);
    }
  }

  const version = net.isIP(normalized);
  if (version === 4) return isPrivateIpv4(normalized);
  if (version === 6) return isPrivateIpv6(normalized);
  return true;
}

async function resolveAll(hostname: string): Promise<Array<{ address: string; family: number }>> {
  const resolved = await dns.promises.lookup(hostname, { all: true, verbatim: true });
  if (!resolved.length) {
    throw new Error('SSRF: DNS resolution returned no records');
  }
  return resolved;
}

function validatePublicAddresses(
  addresses: Array<{ address: string; family: number }>,
  errorPrefix: 'resolved' | 'post-fetch resolved'
): string[] {
  const normalized = addresses.map((a) => stripZoneId(a.address));
  for (const address of normalized) {
    if (isPrivateIp(address)) {
      throw new Error(`SSRF: ${errorPrefix} to private IP ${address}`);
    }
  }
  return [...normalized].sort();
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

  const preLookup = await resolveAll(hostname);
  const preAddresses = validatePublicAddresses(preLookup, 'resolved');

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
  const postLookup = await resolveAll(hostname);
  const postAddresses = validatePublicAddresses(postLookup, 'post-fetch resolved');
  if (
    preAddresses.length !== postAddresses.length ||
    preAddresses.some((ip, idx) => ip !== postAddresses[idx])
  ) {
    throw new Error(
      `SSRF: DNS rebinding detected (${preAddresses.join(',')} -> ${postAddresses.join(',')})`
    );
  }

  const bodyBytes = await readBodyWithinLimit(response, maxBytes);
  return new Response(bodyBytes, {
    status: response.status,
    statusText: response.statusText,
    headers: new Headers(response.headers),
  });
}
