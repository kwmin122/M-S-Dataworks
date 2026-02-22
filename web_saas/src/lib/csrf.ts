import { NextRequest } from 'next/server';

const STATE_CHANGING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function getAllowedOrigins(): string[] {
  const appUrl = (process.env.NEXT_PUBLIC_APP_URL ?? '').trim();
  const origins: string[] = [];

  if (appUrl) origins.push(appUrl);
  if (process.env.NODE_ENV !== 'production') {
    origins.push('http://localhost:3000', 'http://localhost:5173');
  }

  return origins;
}

export function verifyCsrfOrigin(req: NextRequest): boolean {
  if (!STATE_CHANGING_METHODS.has(req.method)) return true;

  const origin = req.headers.get('origin') ?? '';
  if (!origin) return false;

  return getAllowedOrigins().includes(origin);
}
