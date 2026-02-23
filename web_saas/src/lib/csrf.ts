import { NextRequest } from 'next/server';
import { getEnv } from '@/lib/env';

const STATE_CHANGING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function getAllowedOrigins(): string[] {
  const { NEXT_PUBLIC_APP_URL: appUrl, NODE_ENV } = getEnv();
  const origins: string[] = [];

  if (appUrl) origins.push(appUrl.trim());
  if (NODE_ENV !== 'production') {
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
