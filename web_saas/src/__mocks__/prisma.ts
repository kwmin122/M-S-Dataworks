export const prisma = {
  $transaction: jest.fn(),
  $executeRaw: jest.fn(),
  $queryRaw: jest.fn(),
  evaluationJob: {
    findUnique: jest.fn(),
    update: jest.fn(),
    upsert: jest.fn(),
    findMany: jest.fn(),
  },
  subscription: { findUnique: jest.fn() },
  usageQuota: { upsert: jest.fn() },
  organization: { findMany: jest.fn(), findUnique: jest.fn() },
  bidNotice: { findMany: jest.fn() },
  ingestionJob: { findUnique: jest.fn(), update: jest.fn() },
  usedNonce: { create: jest.fn() },
};
