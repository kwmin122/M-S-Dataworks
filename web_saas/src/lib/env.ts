import { z } from 'zod';

const schema = z.object({
  DATABASE_URL: z.string().min(1, 'DATABASE_URL is required'),
  STRIPE_SECRET_KEY: z.string().regex(/^sk_(test|live)_/, 'STRIPE_SECRET_KEY must start with sk_test_ or sk_live_'),
  STRIPE_WEBHOOK_SECRET: z.string().min(1, 'STRIPE_WEBHOOK_SECRET is required'),
  WEBHOOK_SECRET: z.string().min(32, 'WEBHOOK_SECRET must be >= 32 chars'),
  INTERNAL_API_SECRET: z.string().min(32, 'INTERNAL_API_SECRET must be >= 32 chars'),
  NEXTAUTH_SECRET: z.string().min(32, 'NEXTAUTH_SECRET must be >= 32 chars'),
  NEXTAUTH_URL: z.string().url('NEXTAUTH_URL must be a valid URL'),
  FASTAPI_URL: z.string().url().default('http://localhost:8001'),
  ATTACHMENT_ALLOWED_DOMAINS: z.string().default('.go.kr'),
  NEXT_PUBLIC_APP_URL: z.string().default(''),
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
});

export type Env = z.infer<typeof schema>;

let _env: Env | undefined;

export function getEnv(): Env {
  if (!_env) {
    const result = schema.safeParse(process.env);
    if (!result.success) {
      const messages = result.error.issues
        .map((i) => `  ${i.path.join('.')}: ${i.message}`)
        .join('\n');
      throw new Error(`[env] startup validation failed:\n${messages}`);
    }
    _env = result.data;
  }
  return _env;
}

/** 테스트에서만 사용 — env 캐시 초기화 */
export function _resetEnv(): void {
  if (process.env.NODE_ENV === 'production') {
    throw new Error('[env] _resetEnv() must not be called in production');
  }
  _env = undefined;
}
