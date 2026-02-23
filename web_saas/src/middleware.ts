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

  return NextResponse.next();
});

export const config = {
  matcher: ['/api/((?!webhooks|internal|auth).*)'],
};
