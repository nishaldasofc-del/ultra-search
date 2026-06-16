"""
Retry decorator — exponential backoff for flaky external calls
"""

import asyncio
import functools
import logging
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Decorator: retry an async function with exponential backoff."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    logger.warning(f"{func.__name__} attempt {attempt} failed: {e}. Retrying in {current_delay:.1f}s")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator
