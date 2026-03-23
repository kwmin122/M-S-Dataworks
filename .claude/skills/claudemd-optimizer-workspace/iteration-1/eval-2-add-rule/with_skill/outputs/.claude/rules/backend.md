---
paths:
  - "services/**"
  - "*.go"
  - "*.py"
---

## MANDATORY
- Go errors: errors.Wrap with context
- Python: uvicorn + FastAPI pattern
- gRPC for internal service calls, REST for external APIs
- Go gRPC 호출 시 context.WithTimeout 사용 — 모든 gRPC client call에 timeout이 있는 context를 전달 (예: `ctx, cancel := context.WithTimeout(ctx, 5*time.Second)`)

## PREFER
- Structured JSON logging
- Batch inserts for ClickHouse (1000 rows)
