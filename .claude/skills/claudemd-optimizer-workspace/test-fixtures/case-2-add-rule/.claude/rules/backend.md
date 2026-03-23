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

## PREFER
- Structured JSON logging
- Batch inserts for ClickHouse (1000 rows)
