import { prisma } from '@/lib/prisma';

const mockCompare = jest.fn();
const mockCredentials = jest.fn((options: unknown) => options);
const mockNextAuth = jest.fn((config: unknown) => ({
  auth: jest.fn(),
  handlers: { GET: jest.fn(), POST: jest.fn() },
  signIn: jest.fn(),
  signOut: jest.fn(),
  _config: config,
}));

jest.mock('next-auth', () => ({
  __esModule: true,
  default: (config: unknown) => mockNextAuth(config),
}));

jest.mock('next-auth/providers/credentials', () => ({
  __esModule: true,
  default: (options: unknown) => mockCredentials(options),
}));

jest.mock('bcryptjs', () => ({
  __esModule: true,
  default: {
    compare: (...args: unknown[]) => mockCompare(...args),
  },
}));

type AuthConfig = {
  providers: Array<{ authorize: (credentials: unknown) => Promise<unknown> }>;
  callbacks: {
    jwt: (args: { token: Record<string, unknown>; user?: Record<string, unknown> }) => Record<string, unknown>;
    session: (args: { session: { user: Record<string, unknown> }; token: Record<string, unknown> }) => { user: Record<string, unknown> };
  };
};

let config: AuthConfig;

describe('auth.ts', () => {
  beforeAll(async () => {
    await import('@/auth');
    expect(mockNextAuth).toHaveBeenCalledTimes(1);
    config = mockNextAuth.mock.calls[0][0] as AuthConfig;
  });

  beforeEach(() => {
    mockCompare.mockReset();
    (prisma.user.findUnique as jest.Mock).mockReset();
  });

  it('returns null when credentials are missing', async () => {
    const result = await config.providers[0].authorize(undefined);

    expect(result).toBeNull();
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
  });

  it('returns null when user does not exist', async () => {
    (prisma.user.findUnique as jest.Mock).mockResolvedValue(null);

    const result = await config.providers[0].authorize({
      email: 'none@example.com',
      password: 'secret',
    });

    expect(result).toBeNull();
    expect(mockCompare).not.toHaveBeenCalled();
  });

  it('returns null when password does not match', async () => {
    (prisma.user.findUnique as jest.Mock).mockResolvedValue({
      id: 'u1',
      email: 'user@example.com',
      passwordHash: 'hashed',
      organizationId: 'org-1',
    });
    mockCompare.mockResolvedValue(false);

    const result = await config.providers[0].authorize({
      email: 'user@example.com',
      password: 'wrong',
    });

    expect(result).toBeNull();
  });

  it('returns user identity with organizationId when password matches', async () => {
    (prisma.user.findUnique as jest.Mock).mockResolvedValue({
      id: 'u1',
      email: 'user@example.com',
      passwordHash: 'hashed',
      organizationId: 'org-1',
    });
    mockCompare.mockResolvedValue(true);

    const result = await config.providers[0].authorize({
      email: 'user@example.com',
      password: 'secret',
    });

    expect(result).toEqual({
      id: 'u1',
      email: 'user@example.com',
      organizationId: 'org-1',
    });
  });

  it('propagates organizationId to jwt and session callbacks', () => {
    const token = { sub: 'u1' };
    const jwtOut = config.callbacks.jwt({
      token,
      user: { organizationId: 'org-1' },
    });
    expect(jwtOut.organizationId).toBe('org-1');

    const session = { user: { email: 'user@example.com' } };
    const sessionOut = config.callbacks.session({
      session,
      token: { organizationId: 'org-1' },
    });
    expect(sessionOut.user.organizationId).toBe('org-1');
  });
});
