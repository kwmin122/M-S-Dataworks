"""
Redis 기반 세션 저장소 (Hybrid)

- RAGEngine: In-memory (재생성 가능)
- 분석 결과: Redis (영속화 필요)
- Railway 재시작 시 분석 결과 보존
"""

import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Redis 연결 풀 (싱글턴)
_redis_pool: Optional[object] = None
_redis_enabled: Optional[bool] = None

# TTL 설정
ANALYSIS_TTL = 3600 * 4  # 4시간 (분석 결과 보관)


def is_redis_enabled() -> bool:
    """Redis 사용 여부 체크 (환경변수 캐싱)"""
    global _redis_enabled
    if _redis_enabled is None:
        _redis_enabled = os.getenv("REDIS_ENABLED", "0").strip() in {"1", "true", "True", "TRUE"}
        if _redis_enabled:
            logger.info("✅ Redis session storage ENABLED")
        else:
            logger.info("ℹ️  Redis session storage DISABLED (using in-memory only)")
    return _redis_enabled


def get_redis():
    """Redis 연결 반환 (enabled 시에만)"""
    if not is_redis_enabled():
        return None

    global _redis_pool
    if _redis_pool is None:
        try:
            import redis
            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                logger.warning("REDIS_ENABLED=1 but REDIS_URL not set, falling back to in-memory")
                return None

            # 환경변수로 튜닝 가능, Railway 프로덕션 최적화
            max_conn = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
            conn_timeout = int(os.getenv("REDIS_CONNECT_TIMEOUT", "10"))
            sock_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", "10"))

            _redis_pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=max_conn,
                decode_responses=True,  # UTF-8 자동 디코딩
                socket_connect_timeout=conn_timeout,
                socket_timeout=sock_timeout,
                health_check_interval=30,  # 30초마다 연결 상태 확인
            )
            logger.info("Redis connection pool initialized")
        except ImportError:
            logger.warning("redis package not installed, falling back to in-memory")
            return None
        except Exception as e:
            logger.error("Redis connection failed: %s, falling back to in-memory", e)
            return None

    try:
        import redis
        return redis.Redis(connection_pool=_redis_pool)
    except Exception as e:
        logger.error("Redis client creation failed: %s", e)
        return None


def save_analysis_to_redis(session_id: str, analysis_dict: Dict[str, Any]) -> bool:
    """
    RFP 분석 결과를 Redis에 저장 (RAGEngine 제외)

    Args:
        session_id: 세션 ID
        analysis_dict: RFxAnalysisResult를 dict로 변환한 데이터

    Returns:
        bool: 저장 성공 여부
    """
    r = get_redis()
    if r is None:
        return False

    try:
        key = f"session:{session_id}:rfx"
        r.setex(key, ANALYSIS_TTL, json.dumps(analysis_dict, ensure_ascii=False, default=str))
        logger.debug("Analysis saved to Redis: %s", session_id)
        return True

    except Exception as e:
        logger.error("Failed to save analysis to Redis: %s", e)
        return False


def load_analysis_from_redis(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Redis에서 RFP 분석 결과 로드

    Returns:
        dict or None
    """
    r = get_redis()
    if r is None:
        return None

    try:
        key = f"session:{session_id}:rfx"
        data = r.get(key)

        if not data:
            return None

        # TTL 갱신 (활동 시)
        r.expire(key, ANALYSIS_TTL)

        analysis_dict = json.loads(data)
        logger.debug("Analysis loaded from Redis: %s", session_id)
        return analysis_dict

    except Exception as e:
        logger.error("Failed to load analysis from Redis: %s", e)
        return None


def delete_analysis_from_redis(session_id: str) -> bool:
    """Redis에서 분석 결과 삭제"""
    r = get_redis()
    if r is None:
        return False

    try:
        key = f"session:{session_id}:rfx"
        r.delete(key)
        logger.debug("Analysis deleted from Redis: %s", session_id)
        return True

    except Exception as e:
        logger.error("Failed to delete analysis from Redis: %s", e)
        return False


def restore_analysis_from_dict(analysis_dict: Dict[str, Any]) -> "RFxAnalysisResult":
    """
    Dict를 RFxAnalysisResult 객체로 복원

    Args:
        analysis_dict: Redis에서 로드한 dict

    Returns:
        RFxAnalysisResult 객체
    """
    from rfx_analyzer import RFxAnalysisResult, RFxRequirement, RFxEvaluationCriteria, RFxConstraint

    # Requirements 복원
    requirements = []
    for req_data in analysis_dict.get("requirements", []):
        constraints = []
        for c_data in req_data.get("constraints", []):
            constraints.append(RFxConstraint(
                metric=c_data.get("metric", ""),
                op=c_data.get("op", ">="),
                value=c_data.get("value", 0),
                unit=c_data.get("unit", ""),
                raw=c_data.get("raw", ""),
            ))

        req = RFxRequirement(
            category=req_data.get("category", ""),
            description=req_data.get("description", ""),
            is_mandatory=req_data.get("is_mandatory", False),
            detail=req_data.get("detail", ""),
            constraints=constraints,
        )
        requirements.append(req)

    # Evaluation criteria 복원
    evaluation_criteria = []
    for ec_data in analysis_dict.get("evaluation_criteria", []):
        ec = RFxEvaluationCriteria(
            category=ec_data.get("category", ""),
            item=ec_data.get("item", ""),
            score=float(ec_data.get("score", 0.0)),
            detail=ec_data.get("detail", ""),
        )
        evaluation_criteria.append(ec)

    # RFxAnalysisResult 복원
    analysis = RFxAnalysisResult(
        title=analysis_dict.get("title", ""),
        issuing_org=analysis_dict.get("issuing_org", ""),
        announcement_number=analysis_dict.get("announcement_number", ""),
        deadline=analysis_dict.get("deadline", ""),
        project_period=analysis_dict.get("project_period", ""),
        budget=analysis_dict.get("budget", ""),
        requirements=requirements,
        evaluation_criteria=evaluation_criteria,
    )

    # 추가 필드
    analysis.raw_text = analysis_dict.get("raw_text", "")
    analysis.document_type = analysis_dict.get("document_type", "")
    analysis.is_rfx_like = analysis_dict.get("is_rfx_like", True)
    analysis.document_gate_reason = analysis_dict.get("document_gate_reason", "")
    analysis.document_gate_confidence = float(analysis_dict.get("document_gate_confidence", 0.0))
    analysis.extraction_model = analysis_dict.get("extraction_model", "")

    return analysis
