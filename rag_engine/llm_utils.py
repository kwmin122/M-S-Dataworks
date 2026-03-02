"""LLM 호출 유틸: retry + timeout."""

import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")

_RETRIABLE_STATUS_CODES = {429, 500, 502, 503}
LLM_DEFAULT_TIMEOUT = 60


def call_with_retry(
    fn: Callable[..., T],
    *args,
    max_retries: int = 2,
    base_delay: float = 1.0,
    **kwargs,
) -> T:
    """OpenAI API 호출을 retry + timeout 으로 래핑.

    - APITimeoutError, APIConnectionError → 재시도
    - APIStatusError 429/500/502/503 → 재시도
    - 그 외 상태 코드 → 즉시 raise
    - 지수 백오프: base_delay * 2^attempt (1초, 2초)
    """
    from openai import APIConnectionError, APIStatusError, APITimeoutError

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except (APITimeoutError, APIConnectionError) as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "LLM transient error (attempt %d/%d), retry in %.1fs: %s",
                    attempt + 1,
                    max_retries + 1,
                    delay,
                    exc,
                )
                time.sleep(delay)
            continue
        except APIStatusError as exc:
            last_exc = exc
            if exc.status_code in _RETRIABLE_STATUS_CODES and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "LLM status %d (attempt %d/%d), retry in %.1fs",
                    exc.status_code,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                time.sleep(delay)
                continue
            raise
    raise last_exc  # type: ignore[misc]
