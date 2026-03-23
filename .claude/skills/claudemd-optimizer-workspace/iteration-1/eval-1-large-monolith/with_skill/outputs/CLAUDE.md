# ShopFlow

E-commerce platform with real-time inventory management, payment processing, and analytics dashboard.
Current: Monolith (Next.js + Prisma) migrating to microservices. Vision: Full headless commerce by Q4 2026.

## CRITICAL

- **Existing `/api/orders` and `/api/products` endpoints**: preserve backward compatibility on any change
- **Secrets safety**: use AWS Secrets Manager; never commit .env files or log passwords/tokens/PII
- **Environment variables**: access via `getEnv()` wrapper with zod validation (not `process.env` directly)
- **SQL injection prevention**: use Prisma parameterized queries for all database access

## Commands

### Frontend (Next.js, port 3000)
```bash
cd frontend && npm install
npm run dev
npm run build
npm run test         # Jest + RTL
npm run test:e2e     # Playwright
npm run lint         # ESLint + Prettier
```

### Inventory Service (Go, port 8080)
```bash
cd services/inventory
go run cmd/server/main.go
go test ./...
go test -race ./...
```

### Analytics Service (Python, port 8001)
```bash
cd services/analytics
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
pytest -q
```

### Notification Service (Node.js, port 8002)
```bash
cd services/notification && npm install
npm run dev
npm test
```

### Infrastructure
```bash
docker-compose up -d                                  # PostgreSQL, Redis, ClickHouse
docker-compose -f docker-compose.test.yml up          # Test DBs
cd infra/terraform && terraform plan
```

## Architecture

```
frontend/                  <- Next.js 15 + React 19 (App Router)
  src/app/                 <- Pages
  src/components/          <- Shared UI
  src/lib/                 <- prisma.ts, auth.ts, stripe.ts, redis.ts
  src/middleware.ts         <- Auth + CSRF
services/
  inventory/               <- Go gRPC + REST (port 8080)
  analytics/               <- Python FastAPI + ClickHouse (port 8001)
  notification/            <- Node.js email + push + SMS (port 8002)
db/migrations/             <- Prisma migrations
infra/                     <- docker-compose, k8s, terraform
```

### Data Flow
```
User -> Next.js -> Prisma -> PostgreSQL (orders, users, products)
                -> Redis (session, cache, rate limit)
                -> Stripe (payments)
     -> Inventory Service -> PostgreSQL (stock) + Redis (pub/sub)
     -> Analytics Service -> ClickHouse (events, metrics)
     -> Notification Service -> SES (email) + FCM (push)
```

## Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| DATABASE_URL | Frontend | PostgreSQL connection |
| REDIS_URL | All | Redis connection |
| NEXTAUTH_SECRET | Frontend | JWT signing (>=32 chars) |
| NEXTAUTH_URL | Frontend | Auth callback URL |
| STRIPE_SECRET_KEY | Frontend | Stripe API |
| STRIPE_WEBHOOK_SECRET | Frontend | Stripe webhook signing |
| CLICKHOUSE_URL | Analytics | ClickHouse connection |
| SES_REGION | Notification | AWS SES region |
| FCM_PROJECT_ID | Notification | Firebase project |
| INVENTORY_GRPC_ADDR | Frontend | Inventory service address |

## Current Work

- **Push notifications**: FCM integration in progress
- **Analytics dashboard**: Basic metrics done, charts pending
- **Upcoming**: Multi-currency UI, Wishlist API, Reviews/ratings (Phase 2), Elasticsearch, Mobile (Phase 3)

## CRITICAL (reminder)

- Access environment variables through `getEnv()` with zod — every session
- Protect secrets: AWS Secrets Manager, no .env commits, no PII in logs
- Use Prisma parameterized queries — no string concatenation for SQL
- Preserve existing API endpoint contracts
