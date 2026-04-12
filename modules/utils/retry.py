"""
modules/utils/retry.py
Retry decorator với exponential backoff cho Snapchat Automation Platform
"""

import time
import random
import asyncio
from functools import wraps
from typing import Callable, Optional, Type, Tuple, Any

from loguru import logger


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    jitter: bool = True,
):
    """
    Decorator retry với exponential backoff.

    Args:
        max_attempts : Số lần thử tối đa (bao gồm lần đầu)
        delay        : Thời gian chờ ban đầu (giây)
        backoff      : Hệ số nhân backoff
        exceptions   : Tuple exception classes cần retry
        on_retry     : Callback mỗi lần retry (exception, attempt)
        jitter       : Thêm random ±20% jitter để tránh thundering herd
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        logger.error(
                            f"[{func.__name__}] Đã thử {max_attempts} lần, bỏ qua. "
                            f"Lỗi cuối: {e}"
                        )
                        raise

                    wait = delay * (backoff ** (attempt - 1))
                    if jitter:
                        wait = wait * random.uniform(0.8, 1.2)

                    logger.warning(
                        f"[{func.__name__}] Lần thử {attempt}/{max_attempts} thất bại: {e}. "
                        f"Thử lại sau {wait:.1f}s..."
                    )

                    if on_retry:
                        on_retry(e, attempt)
                    time.sleep(wait)

            if last_exc:
                raise last_exc

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        logger.error(
                            f"[{func.__name__}] Đã thử {max_attempts} lần, bỏ qua. "
                            f"Lỗi cuối: {e}"
                        )
                        raise

                    wait = delay * (backoff ** (attempt - 1))
                    if jitter:
                        wait = wait * random.uniform(0.8, 1.2)

                    logger.warning(
                        f"[{func.__name__}] Lần thử {attempt}/{max_attempts} thất bại: {e}. "
                        f"Thử lại sau {wait:.1f}s..."
                    )

                    if on_retry:
                        on_retry(e, attempt)
                    await asyncio.sleep(wait)

            if last_exc:
                raise last_exc

        # Chọn wrapper phù hợp dựa trên async signature
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def random_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """Sleep ngẫu nhiên trong khoảng [min, max] giây."""
    t = random.uniform(min_sec, max_sec)
    time.sleep(t)
    return t


async def async_random_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """Async sleep ngẫu nhiên trong khoảng [min, max] giây."""
    t = random.uniform(min_sec, max_sec)
    await asyncio.sleep(t)
    return t
