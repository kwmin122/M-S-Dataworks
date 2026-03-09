# Redis 세션 영속화 설계

**날짜**: 2026-03-09  
**목적**: Railway 재시작 시 세션 보존 + 멀티 인스턴스 지원

---

## 현재 문제

### In-Memory 세션 (services/web_app/main.py)
```python
SESSIONS: dict[str, WebRuntimeSession] = {}
```

**문제점**:
1. **Railway 재시작 시 모든 세션 손실**
   - 사용자가 업로드한 회사 문서 사라짐
   - 분석 결과 (`latest_rfx_analysis`) 손실
   - 제안서 생성 불가 (세션 데이터 없음)

2. **멀티 인스턴스 불가**
   - 요청이 다른 인스턴스로 가면 세션 없음
   - 로드 밸런싱 불가능

3. **메모리 누수 위험**
   - 만료된 세션도 메모리에 계속 존재
   - `_cleanup_expired_sessions()` 호출 시점 불확실

---

## Redis 설계

### 1. 데이터 구조

#### 세션 키 패턴
```
session:{session_id}       # 세션 메타데이터 (JSON)
session:{session_id}:rfx   # RFP 분석 결과 (JSON)
session:{session_id}:docs  # 업로드된 문서 목록 (List)
```

#### TTL 전략
```python
SESSION_TTL = 3600 * 2  # 2시간 (활동 시 갱신)
ANALYSIS_TTL = 3600 * 24  # 24시간 (분석 결과는 더 오래 보관)
```

#### 세션 스키마 (JSON)
```json
{
  "session_id": "unique_id",
  "created_at": 1773033000,
  "last_accessed": 1773034800,
  "user_email": "optional",
  "company_name": "optional",
  "rfx_analysis_key": "session:abc:rfx"
}
```

### 2. Redis 연결

#### 환경 변수
```bash
# Local: Redis 미사용 (기존 in-memory 유지)
REDIS_ENABLED=0

# Railway: Redis 사용
REDIS_ENABLED=1
REDIS_URL=redis://default:password@host:port
```

#### 연결 풀
```python
import redis
from typing import Optional

_redis_pool: Optional[redis.ConnectionPool] = None

def get_redis() -> Optional[redis.Redis]:
    """Redis 연결 반환 (enabled 시에만)"""
    if not os.getenv("REDIS_ENABLED", "0") == "1":
        return None
    
    global _redis_pool
    if _redis_pool is None:
        redis_url = os.getenv("REDIS_URL")
        _redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=10,
            decode_responses=True,  # UTF-8 자동 디코딩
        )
    
    return redis.Redis(connection_pool=_redis_pool)
```

### 3. 세션 CRUD

#### Create/Get
```python
def get_or_create_session_redis(session_id: str) -> WebRuntimeSession:
    """Redis 기반 세션 get/create (fallback to in-memory)"""
    r = get_redis()
    
    if r is None:
        # Fallback: 기존 in-memory
        return _get_or_create_session(session_id)
    
    key = f"session:{session_id}"
    data = r.get(key)
    
    if data:
        # Redis에서 로드
        session_dict = json.loads(data)
        session = WebRuntimeSession(**session_dict)
        
        # TTL 갱신 (활동 시)
        r.expire(key, SESSION_TTL)
        
        # RFP 분석 결과 로드 (별도 키)
        rfx_key = f"{key}:rfx"
        rfx_data = r.get(rfx_key)
        if rfx_data:
            session.latest_rfx_analysis = RFxAnalysisResult(**json.loads(rfx_data))
        
        return session
    else:
        # 신규 생성
        session = WebRuntimeSession(session_id=session_id)
        _save_session_redis(session)
        return session
```

#### Save
```python
def _save_session_redis(session: WebRuntimeSession):
    """세션을 Redis에 저장"""
    r = get_redis()
    if r is None:
        return  # Fallback: in-memory는 자동 저장
    
    key = f"session:{session.session_id}"
    
    # 메타데이터 저장 (RFP 제외)
    session_dict = {
        "session_id": session.session_id,
        "created_at": session.created_at,
        "last_accessed": session.last_accessed,
        "company_name": session.company_name,
        # latest_rfx_analysis는 별도 저장
    }
    
    r.setex(key, SESSION_TTL, json.dumps(session_dict))
    
    # RFP 분석 결과 저장 (크기가 크므로 별도 키)
    if session.latest_rfx_analysis:
        rfx_key = f"{key}:rfx"
        rfx_dict = session.latest_rfx_analysis.__dict__
        r.setex(rfx_key, ANALYSIS_TTL, json.dumps(rfx_dict))
```

#### Delete/Cleanup
```python
def cleanup_expired_sessions_redis():
    """Redis는 TTL 자동 만료 → 수동 cleanup 불필요"""
    # Redis EXPIRE 자동 처리
    pass
```

### 4. 마이그레이션 전략

#### Phase 1: Dual Write (안전 배포)
```python
def save_session(session):
    # In-memory 저장 (기존)
    SESSIONS[session.session_id] = session
    
    # Redis 저장 (신규, 실패해도 무시)
    try:
        _save_session_redis(session)
    except Exception as e:
        logger.warning("Redis save failed (fallback ok): %s", e)
```

#### Phase 2: Redis Primary
```python
def save_session(session):
    # Redis 저장 (primary)
    _save_session_redis(session)
    
    # In-memory는 LRU 캐시로만 사용 (optional)
```

---

## 구현 단계

### Step 1: Redis 클라이언트 추가
```bash
pip install redis>=5.0.0
```

### Step 2: 환경변수 설정
```bash
# Railway 환경변수 추가
REDIS_ENABLED=1
REDIS_URL=redis://...  # Railway Redis 플러그인 URL
```

### Step 3: 세션 어댑터 구현
```
services/web_app/session_store.py  # 신규 파일
  - get_redis()
  - get_or_create_session_redis()
  - _save_session_redis()
  - SessionStore 추상화 클래스
```

### Step 4: main.py 통합
```python
from session_store import get_or_create_session_redis

# 기존: _get_or_create_session()
# 신규: get_or_create_session_redis() 사용
```

### Step 5: 배포 및 검증
- Railway에서 세션 생성 → 재시작 → 세션 복구 확인
- 멀티 인스턴스 테스트 (2+ replicas)

---

## 대안: Redis 없이 해결

### 옵션 A: 파일 기반 세션
```python
# data/sessions/{session_id}.json
# 장점: Redis 불필요
# 단점: 멀티 인스턴스 불가, I/O 병목
```

### 옵션 B: Supabase Storage
```python
# Supabase bucket에 세션 JSON 저장
# 장점: 기존 Supabase 인프라 활용
# 단점: 속도 느림 (HTTP API), 비용
```

### 추천: **Redis** (속도 + 멀티 인스턴스 + TTL 자동 관리)

---

## 예상 효과

### Before (In-Memory)
- ❌ Railway 재시작 → 모든 세션 손실
- ❌ 멀티 인스턴스 불가
- ❌ 메모리 누수 위험

### After (Redis)
- ✅ Railway 재시작 → 세션 유지 (2시간 TTL)
- ✅ 멀티 인스턴스 지원 (로드 밸런싱 가능)
- ✅ 자동 만료 (메모리 관리 불필요)

---

**구현 예상 시간**: 2-3시간  
**우선순위**: P1 (Railway 재시작 문제 해결)
