import { auth } from '@/auth';
import { NextResponse } from 'next/server';
import { verifyCsrfOrigin } from '@/lib/csrf';

export default auth((req) => {
  if (!req.auth) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  if (!verifyCsrfOrigin(req)) {
    return NextResponse.json({ error: 'csrf_origin_mismatch' }, { status: 403 });
  }

  const res = NextResponse.next();

  // Security headers
  res.headers.set('X-Frame-Options', 'DENY');
  res.headers.set('X-Content-Type-Options', 'nosniff');
  res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.headers.set('Permissions-Policy', 'geolocation=(), microphone=(), camera=()');
  res.headers.set(
    'Strict-Transport-Security',
    'max-age=31536000; includeSubDomains; preload'
  );
  res.headers.set(
    'Content-Security-Policy',
    "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self';"
  );

  return res;
});

export const config = {
  matcher: ['/api/((?!webhooks|internal|auth).*)'],
};
