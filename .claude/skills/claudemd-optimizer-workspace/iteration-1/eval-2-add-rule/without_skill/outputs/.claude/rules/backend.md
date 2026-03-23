---
paths:
  - "services/**"
  - "*.go"
  - "*.py"
---

## MANDATORY
- Go errors: errors.Wrap with context
- Python: uvicorn + FastAPI pattern
- gRPC for internal service calls
- REST for external APIs
- Go gRPC 호출 시 `context.WithTimeout` 필수 — 타임아웃 없는 gRPC 콜 금지. 모든 gRPC client call에 deadline이 있는 context를 전달할 것

## PREFER
- Structured JSON logging
- Batch inserts for ClickHouse (1000 rows)
