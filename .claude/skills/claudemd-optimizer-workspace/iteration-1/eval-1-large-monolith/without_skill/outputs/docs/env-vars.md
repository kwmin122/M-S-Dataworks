# Environment Variables

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
