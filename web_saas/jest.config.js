/** @type {import('jest').Config} */
const config = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/__tests__/**/*.test.ts'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  moduleNameMapper: {
    '^@/lib/prisma$': '<rootDir>/src/__mocks__/prisma.ts',
    '^@/lib/ids$': '<rootDir>/src/__mocks__/ids.ts',
    '^@/(.*)$': '<rootDir>/src/$1',
  },
};

module.exports = config;
