# ShopFlow

E-commerce platform with real-time inventory, payments, and analytics.

## CRITICAL
- Stripe webhook endpoint 절대 삭제 금지 — 결제 누락 발생
- 재고 차감은 반드시 Redis lock + DB transaction 동시 사용

## Commands
```bash
# Frontend
cd frontend && npm run dev

# Services
docker-compose up -d
cd services/inventory && go run cmd/server/main.go
cd services/analytics && uvicorn main:app --reload --port 8001
```

## Environment Variables
| Variable | Description |
|----------|-------------|
| DATABASE_URL | PostgreSQL |
| REDIS_URL | Redis |
| STRIPE_SECRET_KEY | Stripe |
| NEXTAUTH_SECRET | JWT signing |

## Current Work
Analytics dashboard v2 — ClickHouse materialized views

## CRITICAL (reminder)
- Stripe webhook 삭제 금지
- 재고: Redis lock + DB transaction
