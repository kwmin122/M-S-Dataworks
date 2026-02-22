import { _resetEnv, getEnv } from '../env';

const REQUIRED_VARS = {
  DATABASE_URL: 'postgresql://x',
  STRIPE_SECRET_KEY: 'sk_test_abc',
  STRIPE_WEBHOOK_SECRET: 'whsec_abc',
  WEBHOOK_SECRET: 'a'.repeat(32),
  INTERNAL_API_SECRET: 'b'.repeat(32),
  NEXTAUTH_SECRET: 'c'.repeat(32),
  NEXTAUTH_URL: 'http://localhost:3000',
};

beforeEach(() => {
  _resetEnv();
  Object.keys(REQUIRED_VARS).forEach((k) => delete process.env[k]);
});

afterEach(() => {
  _resetEnv();
});

it('필수 변수 누락 시 ZodError throw', () => {
  expect(() => getEnv()).toThrow(/startup validation failed/);
});

it('모든 필수 변수 있으면 통과', () => {
  Object.assign(process.env, REQUIRED_VARS);
  const env = getEnv();
  expect(env.DATABASE_URL).toBe('postgresql://x');
  expect(env.FASTAPI_URL).toBe('http://localhost:8001'); // default
});

it('WEBHOOK_SECRET 32자 미만이면 실패', () => {
  Object.assign(process.env, { ...REQUIRED_VARS, WEBHOOK_SECRET: 'short' });
  expect(() => getEnv()).toThrow();
});
