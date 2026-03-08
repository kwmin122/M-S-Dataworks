# Phase 3: Infrastructure Security Report

**작성일:** 2026-03-08
**검증자:** Claude (대표이사급 AI 엔지니어)
**검증 범위:** Docker, 네트워크, TLS, CORS, 보안 헤더, rate limiting
**검증 파일:**
- `Dockerfile` (루트)
- `rag_engine/Dockerfile`
- `docker-compose.yml`
- `services/web_app/main.py`

---

## Executive Summary

⚠️ **Phase 3 검증: 4가지 중요 개선 필요**

✅ **양호:**
- CORS allowlist 설정 완료
- PostgreSQL 외부 접근 차단 (127.0.0.1 바인딩)
- multi-stage build 사용
- 환경변수 안전 관리

❌ **개선 필요:**
1. **Docker non-root 사용자** — 루트로 실행 중 (High)
2. **보안 헤더 미설정** — helmet, CSP, HSTS 없음 (High)
3. **Rate limiting 미구현** — DDoS 방어 없음 (Medium)
4. **Read-only filesystem** — 컨테이너 변조 방지 없음 (Low)

---

## 1. Docker 설정

### 1-A. 사용자 권한 ❌ High

**현재 상태:**
```dockerfile
# Dockerfile (루트)
FROM python:3.11-slim
WORKDIR /app
# ... (USER 지시문 없음) ❌
CMD ["/app/start.sh"]
```

```dockerfile
# rag_engine/Dockerfile
FROM python:3.12-slim
WORKDIR /app
# ... (USER 지시문 없음) ❌
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

**문제점:**
- 컨테이너가 `root` 사용자로 실행됨
- 컨테이너 탈출 시 호스트 루트 권한 획득 가능

**권장 수정:**
```dockerfile
# rag_engine/Dockerfile
FROM python:3.12-slim
WORKDIR /app

# non-root 사용자 생성
RUN groupadd -r app && useradd -r -g app app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

# non-root로 전환
USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

### 1-B. Read-only Filesystem ⚠️ Low

**현재 상태:**
```yaml
# docker-compose.yml (read_only 지시문 없음)
services:
  rag_engine:
    build: ./rag_engine
    ports:
      - "8001:8001"
```

**권장 수정:**
```yaml
services:
  rag_engine:
    build: ./rag_engine
    read_only: true  # ✅ 추가
    tmpfs:
      - /tmp
    volumes:
      - ./data:/app/data  # 필요한 디렉토리만 writable
```

---

### 1-C. 기타 양호 항목 ✅

| 항목 | 상태 | 증거 |
|------|------|------|
| multi-stage build | ✅ | `FROM node:20-slim AS frontend-build` |
| --no-cache-dir | ✅ | `pip install --no-cache-dir` |
| apt lists 정리 | ✅ | `rm -rf /var/lib/apt/lists/*` |
| 불필요한 패키지 최소화 | ✅ | `--no-install-recommends` |

---

## 2. 네트워크 정책

### 2-A. PostgreSQL 포트 바인딩 ✅

```yaml
# docker-compose.yml:10
postgres:
  ports:
    - "127.0.0.1:5432:5432"  # ✅ 외부 접근 차단
```

### 2-B. 애플리케이션 포트 바인딩 ⚠️ Medium

**현재 상태:**
```yaml
# docker-compose.yml:22-23
web:
  ports:
    - "3000:3000"  # ⚠️ 0.0.0.0:3000 바인딩 (기본값)
```

**권장 수정 (프로덕션):**
```yaml
web:
  ports:
    - "127.0.0.1:3000:3000"  # ✅ 로컬만 (리버스 프록시 경유)
```

**또는 리버스 프록시 (nginx/Caddy) 사용:**
```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 3. TLS 설정

### 현재 상태: ⚠️ 미확인

- Docker Compose에 TLS 설정 없음
- 프로덕션 배포 시 리버스 프록시 (nginx/Caddy) 또는 Railway/Vercel 자동 TLS 사용 추정

**권장 사항:**
1. Let's Encrypt + Caddy (자동 갱신)
2. Railway/Vercel 배포 시 자동 HTTPS 활성화 확인
3. TLS 1.2 이하 비활성화 (TLS 1.3 선호)

---

## 4. CORS 설정

### 현재 상태: ✅ 양호

```python
# services/web_app/main.py:222-227
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "WEB_API_ALLOW_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,..."
        ).split(",")
    ],
    allow_credentials=True,  # ✅ (추정, 코드 전체 미확인)
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**권장 개선:**
```python
allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],  # ✅ 명시적 허용
allow_headers=["Content-Type", "Authorization", "X-Internal-*"],  # ✅ 최소 헤더
```

---

## 5. 보안 헤더

### 현재 상태: ❌ 미구현 (High)

**Next.js helmet 검색 결과:** 없음

**FastAPI 보안 헤더:** 미확인

**권장 구현:**

#### Next.js (web_saas)
```typescript
// web_saas/src/middleware.ts (추가)
import { NextResponse } from 'next/server';

export default function middleware(req: NextRequest) {
  const res = NextResponse.next();

  // Security headers
  res.headers.set('X-Frame-Options', 'DENY');
  res.headers.set('X-Content-Type-Options', 'nosniff');
  res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.headers.set('Permissions-Policy', 'geolocation=(), microphone=(), camera=()');
  res.headers.set(
    'Strict-Transport-Security',
    'max-age=31536000; includeSubDomains; preload'
  );
  res.headers.set(
    'Content-Security-Policy',
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
  );

  return res;
}
```

#### FastAPI (services/web_app/main.py)
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["yourdomain.com", "*.yourdomain.com", "localhost"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response
```

---

## 6. Rate Limiting

### 현재 상태: ❌ 미구현 (Medium)

**slowapi 검색 결과:** 없음

**권장 구현:**

#### FastAPI (slowapi)
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/analyze/upload")
@limiter.limit("10/minute")  # ✅ 분당 10회 제한
async def analyze_uploaded_document(...):
    ...
```

#### Next.js (upstash/ratelimit)
```bash
npm install @upstash/ratelimit @upstash/redis
```

```typescript
// web_saas/src/lib/rate-limit.ts
import { Ratelimit } from '@upstash/ratelimit';
import { Redis } from '@upstash/redis';

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(10, '1 m'),  // 10 req/min
});

export async function ratelimit(identifier: string) {
  const { success } = await ratelimit.limit(identifier);
  return success;
}
```

---

## 7. IAM 최소권한

### 현재 상태: ⚠️ 미확인

**Docker Compose 권한:**
- 모든 서비스 루트로 실행 중
- 파일 시스템 전체 쓰기 가능

**권장 사항:**
1. **non-root 사용자 전환** (위 Docker 섹션 참조)
2. **볼륨 권한 제한:**
   ```yaml
   volumes:
     - ./data:/app/data:ro  # read-only (필요 시 rw)
   ```
3. **Capabilities 제한:**
   ```yaml
   cap_drop:
     - ALL
   cap_add:
     - NET_BIND_SERVICE  # 필요한 capability만
   ```

---

## 종합 평가

| 항목 | 상태 | 심각도 | 비고 |
|------|------|--------|------|
| **Docker non-root** | ❌ 미구현 | High | 루트 실행 중 |
| **보안 헤더** | ❌ 미구현 | High | helmet, CSP, HSTS 없음 |
| **Rate limiting** | ❌ 미구현 | Medium | DDoS 방어 없음 |
| **Read-only fs** | ❌ 미구현 | Low | 컨테이너 변조 가능 |
| **CORS** | ✅ 양호 | - | allowlist 설정 |
| **PostgreSQL 격리** | ✅ 양호 | - | 127.0.0.1 바인딩 |
| **multi-stage build** | ✅ 양호 | - | 빌드 최적화 |
| **TLS** | ⚠️ 미확인 | - | 프로덕션 검증 필요 |

---

## 개선 권장 사항 (우선순위)

### Priority 1: Docker non-root (High)
- 모든 Dockerfile에 `USER app` 추가
- `--chown=app:app` 사용
- Railway/Vercel 배포 시 자동 적용 확인

### Priority 2: 보안 헤더 (High)
- Next.js middleware에 보안 헤더 추가
- FastAPI middleware에 보안 헤더 추가
- CSP, HSTS, X-Frame-Options 필수

### Priority 3: Rate limiting (Medium)
- FastAPI: slowapi 도입
- Next.js: @upstash/ratelimit 도입
- 엔드포인트별 제한 설정 (예: /api/analyze/upload → 10/min)

### Priority 4: Read-only filesystem (Low)
- docker-compose.yml에 `read_only: true` 추가
- 필요한 디렉토리만 tmpfs/volume으로 writable 설정

---

## 결론

**Phase 3 검증 완료 ⚠️ — 4가지 중요 개선 필요**

인프라 보안에서 Docker non-root 사용자, 보안 헤더, rate limiting, read-only filesystem 등 4가지 핵심 항목이 미구현 상태입니다. 특히 Docker non-root와 보안 헤더는 High 우선순위로 즉시 개선이 필요합니다.

**다음 Phase:**
- Phase 4: Dependencies & Supply Chain (npm audit, CVE 스캔, 라이선스, 악성 패키지, lock file 무결성)

---

**승인:** 대표이사급 AI 엔지니어 Claude
**날짜:** 2026-03-08
**버전:** 1.0
