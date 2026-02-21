export const prisma = {
  $transaction: jest.fn(),
  evaluationJob: {
    findUnique: jest.fn(),
    update: jest.fn(),
    upsert: jest.fn(),
  },
  subscription: { findUnique: jest.fn() },
  usageQuota: { upsert: jest.fn() },
  organization: { findMany: jest.fn() },
};
