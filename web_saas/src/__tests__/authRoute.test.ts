import fs from 'fs';
import path from 'path';

describe('auth integration', () => {
  it('adds auth.ts and NextAuth route handler files', () => {
    const root = process.cwd();
    const authPath = path.join(root, 'src', 'auth.ts');
    const routePath = path.join(
      root,
      'src',
      'app',
      'api',
      'auth',
      '[...nextauth]',
      'route.ts'
    );

    expect(fs.existsSync(authPath)).toBe(true);
    expect(fs.existsSync(routePath)).toBe(true);

    const authCode = fs.readFileSync(authPath, 'utf8');
    const routeCode = fs.readFileSync(routePath, 'utf8');

    expect(authCode).toContain("import NextAuth from 'next-auth'");
    expect(authCode).toContain("import Credentials from 'next-auth/providers/credentials'");
    expect(authCode).toContain('session: { strategy: \'jwt\' }');
    expect(routeCode).toContain("import { handlers } from '@/auth';");
    expect(routeCode).toContain('export const { GET, POST } = handlers;');
  });
});
