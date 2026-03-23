---
paths:
  - "services/**"
  - "*.go"
  - "*.py"
---

## CRITICAL

- **Inventory (Go)**: use `context.WithCancel` for graceful shutdown (not `os.Exit`)
- **Analytics (Python)**: ClickHouse batch inserts of 1000 rows (not one-by-one)
- **Secrets**: use AWS Secrets Manager (never commit .env or log sensitive data)

## MANDATORY

### Inventory Service (Go)
- Error handling: `errors.Wrap` with context message
- Concurrency: channel-based communication (use mutexes only when channels are impractical)
- Configuration: Viper + environment variables
- Dependency injection: wire (not global variables)
- Internal service communication: gRPC (not REST)

### Analytics Service (Python)
- Data retention: 90 days in ClickHouse, 7 days in Redis
- Aggregation: materialized views for common queries (not compute-on-the-fly)
- Export format: Parquet (not CSV for large datasets)

### Notification Service (Node.js)
- Email: AWS SES
- Push: Firebase FCM
- Templates: `src/templates/` directory

## PREFER

- Structured JSON logs in production (not `console.log` / `fmt.Println`)
- Docker multi-stage builds excluding dev dependencies from prod images
- Datadog APM + custom metrics with alerting configured

## Architecture

```
services/
  inventory/
    cmd/server/main.go       <- gRPC + REST gateway (port 8080)
    internal/                 <- Domain logic (stock, reservation)
    pkg/                      <- Shared packages (grpc server)
  analytics/
    main.py                   <- FastAPI (port 8001)
    clickhouse_client.py      <- ClickHouse queries
  notification/
    src/index.ts              <- Email + Push + SMS (port 8002)
    src/templates/            <- Email templates
```

## CRITICAL (reminder)

- Go graceful shutdown with `context.WithCancel`
- ClickHouse batch inserts (1000 rows), never single-row
- Secrets in AWS Secrets Manager, never in code or logs
