---
paths:
  - "db/**"
  - "src/lib/**"
  - "src/app/api/**"
---

## CRITICAL

- SQL: use Prisma parameterized queries (never string concatenation)
- Secrets: access via `getEnv()` with zod (not `process.env` directly)

## MANDATORY

### Database
- **ID generation**: `createId()` (cuid2) — not auto-increment or UUID
- **Timestamps**: always UTC — not local timezone
- **Soft delete**: `deletedAt` column — not hard DELETE
- **Transactions**: `Prisma.$transaction` for multi-table operations
- **Indexes**: add index on all foreign keys; use compound indexes for common queries
- **Connection pool**: max 20 connections; load-test before increasing

### API Design
- External APIs: REST
- Internal service-to-service: gRPC
- Request validation: zod schemas on every endpoint
- Error response format: `{ error: string, code: string, details?: any }` (no stack traces)
- Pagination: cursor-based (not offset-based for large datasets)
- Rate limiting: per-user sliding window (not fixed window)

### Authentication
- Session: NextAuth v5 JWT strategy
- CSRF: Origin-based middleware check on all mutation routes
- Tokens: HttpOnly + Secure + SameSite=Lax cookies
- Rate limit: Redis sliding window, 100 req/min

## PREFER

- Keep API endpoint contracts stable; version-breaking changes with `/v2/` prefix
- All PRs require at least 1 review before merge
- CI must pass before merge to main; no direct pushes to main

## CRITICAL (reminder)

- Prisma parameterized queries only — no SQL string concatenation
- `createId()` for all new IDs — no auto-increment or UUID
