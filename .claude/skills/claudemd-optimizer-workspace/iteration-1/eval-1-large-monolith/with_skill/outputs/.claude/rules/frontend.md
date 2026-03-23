---
paths:
  - "frontend/**"
  - "*.tsx"
  - "*.ts"
  - "e2e/**"
---

## CRITICAL

- Use `getEnv()` wrapper with zod for environment variables (not `process.env.*` directly)
- Use HttpOnly + Secure + SameSite=Lax cookies for tokens (not localStorage)

## MANDATORY

- **State management**: React Query for server state, zustand for client state
- **Forms**: React Hook Form + zod resolver
- **Styling**: Tailwind CSS only
- **Images**: next/image with S3 CDN (not raw `<img>` tags)
- **i18n**: next-intl for all user-facing strings
- **Auth**: NextAuth v5 with JWT strategy
- **CSRF**: Origin-based check in middleware applies to all routes
- **TypeScript**: use explicit types (not `any`)
- **Async**: always handle errors in async functions
- **Rate limiting**: Redis sliding window at 100 req/min

## PREFER

- Reuse existing Tailwind classes over creating new ones
- Conventional commit format for commit messages
- Branch naming: `feature/*`, `fix/*`, `chore/*`
- Link a GitHub issue for every TODO comment

## Architecture

```
frontend/
  src/app/           <- App Router pages
  src/components/    <- Shared UI components
  src/hooks/         <- useCart, useInventory, etc.
  src/lib/           <- prisma.ts, auth.ts, stripe.ts, redis.ts
  src/middleware.ts   <- Auth + CSRF protection
```

## CRITICAL (reminder)

- Tokens in HttpOnly cookies only — never localStorage
- Environment variables through `getEnv()` with zod validation
