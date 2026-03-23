# CLAUDE.md

**ShopFlow** — E-commerce platform (real-time inventory, payments, analytics). Monolith (Next.js + Prisma) migrating to microservices. Target: headless commerce by Q4 2026.

## Architecture

```
frontend/              Next.js 15 + React 19 (port 3000)
  src/app/             App Router pages
  src/components/      Shared UI
  src/hooks/           Custom hooks
  src/lib/             prisma.ts | auth.ts (NextAuth v5) | stripe.ts | redis.ts
  src/middleware.ts    Auth + CSRF
services/
  inventory/           Go gRPC+REST (port 8080) — cmd/server/main.go, internal/, pkg/
  analytics/           Python FastAPI (port 8001) — main.py, clickhouse_client.py
  notification/        Node.js (port 8002) — email + push + SMS
db/migrations/         Prisma migrations
infra/                 docker-compose.yml | k8s/ | terraform/
```

**Data flow:** User -> Next.js -> Prisma/PostgreSQL + Redis(cache/session) + Stripe(payments) -> Inventory(Go/PostgreSQL/Redis pub-sub) -> Analytics(ClickHouse) -> Notifications(SES/FCM)

## Commands

```bash
# Frontend
cd frontend && npm install && npm run dev        # port 3000
npm run test         # Jest + RTL
npm run test:e2e     # Playwright
npm run lint         # ESLint + Prettier

# Inventory (Go)
cd services/inventory && go run cmd/server/main.go  # port 8080
go test ./...        # add -race for race detection

# Analytics (Python)
cd services/analytics && pip install -r requirements.txt
uvicorn main:app --reload --port 8001
pytest -q

# Notification (Node.js)
cd services/notification && npm install && npm run dev  # port 8002
npm test

# Infrastructure
docker-compose up -d                                    # PostgreSQL, Redis, ClickHouse
docker-compose -f docker-compose.test.yml up             # Test DBs
cd infra/terraform && terraform plan
```

## Design Rules

### Database
- IDs: `createId()` (cuid2) -- no auto-increment/UUID
- Timestamps: always UTC -- no local timezone
- Soft delete via `deletedAt` -- no hard DELETE
- Multi-table writes: `Prisma.$transaction` -- no separate queries
- Always index foreign keys + compound indexes for common queries
- Connection pool max 20 -- load test before increasing

### Auth & Security
- NextAuth v5 JWT strategy -- no database sessions
- CSRF: Origin-based middleware check on all routes including API
- Env vars: `getEnv()` zod wrapper -- no direct `process.env`
- Cookies: HttpOnly + Secure + SameSite=Lax -- no localStorage tokens
- Rate limit: Redis sliding window 100 req/min -- no in-memory store in prod

### API
- External: REST. Internal service-to-service: gRPC
- Validation: zod schemas -- never trust client input
- Error format: `{ error, code, details? }` -- no stack traces
- Pagination: cursor-based -- no offset for large datasets
- Rate limiting: per-user sliding window -- no fixed window

### Frontend
- Server state: React Query. Client state: zustand. No Redux
- Forms: React Hook Form + zod resolver
- Styling: Tailwind CSS only -- no CSS modules/styled-components
- Images: next/image + S3 CDN -- no raw `<img>`
- i18n: next-intl -- no hardcoded strings
- Tests: Jest + RTL (unit), Playwright (E2E)

### Go (Inventory)
- Errors: `errors.Wrap` with context -- no bare `errors.New`
- Concurrency: channels preferred -- mutexes only when necessary
- Config: Viper + env vars -- no hardcoded values
- Shutdown: `context.WithCancel` -- no `os.Exit`
- DI: wire -- no global variables

### Analytics (ClickHouse)
- Batch inserts of 1000 -- no single-row inserts
- Retention: 90d ClickHouse, 7d Redis -- no unlimited raw events
- Common queries: materialized views -- no on-the-fly computation
- Export: Parquet -- no CSV for large datasets

### Infra
- Docker: multi-stage builds -- no dev deps in prod images
- Secrets: AWS Secrets Manager -- no committed .env files
- Logging: structured JSON -- no console.log in prod
- Monitoring: Datadog APM + alerts
- CI/CD: GitHub Actions -- all checks must pass before deploy

## Coding Standards

- PRs require 1+ review; no direct push to main
- Branches: `feature/*`, `fix/*`, `chore/*`; conventional commits
- No `any` TypeScript type
- No skipping async error handling
- No string concatenation for SQL
- No logging sensitive data (passwords, tokens, PII)
- No TODO comments without linked issue

## Env Vars

See `docs/env-vars.md` for full list. Key ones: `DATABASE_URL`, `REDIS_URL`, `NEXTAUTH_SECRET` (>=32 chars), `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `CLICKHOUSE_URL`, `INVENTORY_GRPC_ADDR`.

## Feature Status

Done: product catalog, cart (Redis-backed), checkout (Stripe), orders, user accounts, inventory tracking (real-time), admin dashboard, email notifications.
WIP: push notifications (FCM), analytics dashboard (charts pending).
TODO: multi-currency, wishlist, reviews/ratings, Elasticsearch search, mobile app (React Native).

## Reference

- Test file mapping: `docs/test-mapping.md`
