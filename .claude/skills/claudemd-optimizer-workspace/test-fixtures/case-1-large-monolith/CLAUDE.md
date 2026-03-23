# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

**ShopFlow** — E-commerce platform with real-time inventory management, payment processing, and analytics dashboard.

Current: Monolith (Next.js + Prisma) migrating to microservices.
Vision: Full headless commerce platform by Q4 2026.

### Architecture

```
frontend/                  <- Next.js 15 + React 19
  src/app/                 <- App Router pages
  src/components/          <- Shared UI components
  src/hooks/               <- Custom hooks
  src/lib/                 <- Utilities
    prisma.ts              <- PrismaClient singleton
    auth.ts                <- NextAuth v5 config
    stripe.ts              <- Stripe SDK wrapper
    redis.ts               <- Redis cache client
  src/middleware.ts         <- Auth + CSRF protection
        |
        v HTTP (port 3000)
services/
  inventory/               <- Go microservice (port 8080)
    cmd/server/main.go     <- gRPC + REST gateway
    internal/              <- Domain logic
    pkg/                   <- Shared packages
  analytics/               <- Python FastAPI (port 8001)
    main.py                <- Analytics API
    clickhouse_client.py   <- ClickHouse queries
  notification/            <- Node.js (port 8002)
    src/index.ts           <- Email + Push + SMS
    src/templates/         <- Email templates

db/
  migrations/              <- Prisma migrations
  seeds/                   <- Seed data

infra/
  docker-compose.yml       <- Local dev stack
  k8s/                     <- Kubernetes manifests
  terraform/               <- AWS infrastructure
```

### Data Flow

```
User -> Next.js -> Prisma -> PostgreSQL (orders, users, products)
                -> Redis (session, cache, rate limit)
                -> Stripe (payments)
     -> Inventory Service -> PostgreSQL (stock levels)
                          -> Redis (real-time stock pub/sub)
     -> Analytics Service -> ClickHouse (events, metrics)
     -> Notification Service -> SES (email) + FCM (push)
```

## Commands

### Frontend (Next.js)
```bash
cd frontend && npm install
npm run dev          # port 3000
npm run build
npm run test         # Jest + RTL
npm run test:e2e     # Playwright
npm run lint         # ESLint + Prettier
```

### Inventory Service (Go)
```bash
cd services/inventory
go run cmd/server/main.go    # port 8080
go test ./...
go test -race ./...
```

### Analytics Service (Python)
```bash
cd services/analytics
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
pytest -q
```

### Notification Service (Node.js)
```bash
cd services/notification
npm install
npm run dev    # port 8002
npm test
```

### Infrastructure
```bash
docker-compose up -d          # PostgreSQL, Redis, ClickHouse
docker-compose -f docker-compose.test.yml up  # Test DBs
cd infra/terraform && terraform plan
```

## Design Decisions

### Database
- ID generation: Use cuid2 via createId() — don't use auto-increment or UUID
- Timestamps: Always UTC — don't use local timezone
- Soft delete: Use deletedAt column — don't actually DELETE rows
- Transactions: Use Prisma $transaction for multi-table ops — don't do separate queries
- Indexes: Always add index on foreign keys — don't forget compound indexes for common queries
- Connection pool: max 20 connections — don't increase without load testing

### Authentication
- Session: NextAuth v5 with JWT strategy — don't use database sessions
- CSRF: Origin-based check in middleware — don't skip for API routes
- Secrets: Use getEnv() wrapper with zod — don't access process.env directly
- Tokens: HttpOnly + Secure + SameSite=Lax cookies — don't store in localStorage
- Rate limit: Redis sliding window (100 req/min) — don't use in-memory store in production

### API Design
- REST for external APIs — don't use GraphQL for simple CRUD
- gRPC for internal service-to-service — don't use REST between microservices
- Request validation: zod schemas — don't trust client input
- Error format: { error: string, code: string, details?: any } — don't return stack traces
- Pagination: cursor-based — don't use offset pagination for large datasets
- Rate limiting: per-user sliding window — don't use fixed window

### Frontend
- State: React Query for server state, zustand for client state — don't use Redux
- Forms: React Hook Form + zod resolver — don't build custom form state
- Styling: Tailwind CSS — don't use CSS modules or styled-components
- Images: next/image with S3 CDN — don't use img tags directly
- i18n: next-intl — don't hardcode strings
- Testing: Jest + RTL for unit, Playwright for E2E — don't use Cypress

### Infrastructure
- Containers: Docker multi-stage builds — don't include dev dependencies in prod images
- Secrets: AWS Secrets Manager — don't commit .env files
- Logging: structured JSON logs — don't use console.log in production
- Monitoring: Datadog APM + custom metrics — don't skip alerting setup
- CI/CD: GitHub Actions — don't deploy without passing all checks

### Inventory Service (Go)
- Error handling: errors.Wrap with context — don't use bare errors.New
- Concurrency: channel-based communication — don't share memory with mutexes unless necessary
- Configuration: Viper + env vars — don't hardcode values
- Graceful shutdown: context.WithCancel — don't use os.Exit
- Dependency injection: wire — don't use global variables

### Analytics
- Batch inserts: ClickHouse batch of 1000 — don't insert one row at a time
- Retention: 90 days in ClickHouse, 7 days in Redis — don't keep raw events forever
- Aggregation: Materialized views for common queries — don't compute on the fly
- Export: Parquet format — don't use CSV for large datasets

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

## Test File Mapping

### Frontend (Jest + RTL)
| File | Target |
|------|--------|
| `src/lib/__tests__/auth.test.ts` | `src/lib/auth.ts` |
| `src/lib/__tests__/stripe.test.ts` | `src/lib/stripe.ts` |
| `src/lib/__tests__/redis.test.ts` | `src/lib/redis.ts` |
| `src/components/__tests__/ProductCard.test.tsx` | `ProductCard.tsx` |
| `src/components/__tests__/CartDrawer.test.tsx` | `CartDrawer.tsx` |
| `src/components/__tests__/CheckoutForm.test.tsx` | `CheckoutForm.tsx` |
| `src/hooks/__tests__/useCart.test.ts` | `useCart.ts` |
| `src/hooks/__tests__/useInventory.test.ts` | `useInventory.ts` |
| `src/app/api/__tests__/orders.test.ts` | `orders/route.ts` |
| `src/app/api/__tests__/products.test.ts` | `products/route.ts` |
| `src/app/api/__tests__/webhooks.test.ts` | `webhooks/stripe/route.ts` |

### Frontend (Playwright E2E)
| File | Target |
|------|--------|
| `e2e/checkout.spec.ts` | Full checkout flow |
| `e2e/inventory.spec.ts` | Stock display + real-time updates |
| `e2e/auth.spec.ts` | Login/register/logout |
| `e2e/admin.spec.ts` | Admin dashboard |

### Inventory Service (Go)
| File | Target |
|------|--------|
| `internal/stock/service_test.go` | Stock management |
| `internal/stock/handler_test.go` | HTTP handlers |
| `internal/reservation/service_test.go` | Stock reservation |
| `pkg/grpc/server_test.go` | gRPC endpoints |

### Analytics (Python)
| File | Target |
|------|--------|
| `tests/test_events.py` | Event ingestion |
| `tests/test_metrics.py` | Metric aggregation |
| `tests/test_export.py` | Data export |

### Notification (Node.js)
| File | Target |
|------|--------|
| `src/__tests__/email.test.ts` | Email sending |
| `src/__tests__/push.test.ts` | Push notifications |
| `src/__tests__/templates.test.ts` | Template rendering |

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| Product catalog | Done | Full CRUD + search |
| Shopping cart | Done | Redis-backed, real-time sync |
| Checkout flow | Done | Stripe Elements integration |
| Order management | Done | Status tracking + webhooks |
| User accounts | Done | NextAuth + profile management |
| Inventory tracking | Done | Real-time stock via Redis pub/sub |
| Admin dashboard | Done | Orders, products, analytics |
| Email notifications | Done | Order confirmation, shipping |
| Push notifications | WIP | FCM integration in progress |
| Analytics dashboard | WIP | Basic metrics, charts pending |
| Multi-currency | TODO | Stripe supports it, UI needed |
| Wishlist | TODO | Schema ready, API needed |
| Reviews/ratings | TODO | Phase 2 |
| Search optimization | TODO | Elasticsearch migration |
| Mobile app | TODO | React Native, Phase 3 |

## Coding Standards

- All PRs require at least 1 review
- Branch naming: feature/*, fix/*, chore/*
- Commit messages: conventional commits format
- Don't merge without CI passing
- Don't push directly to main
- Don't leave TODO comments without a linked issue
- Don't use any as TypeScript type
- Don't skip error handling in async functions
- Don't use string concatenation for SQL queries
- Don't log sensitive data (passwords, tokens, PII)
