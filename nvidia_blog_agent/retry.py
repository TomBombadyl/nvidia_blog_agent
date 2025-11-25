"""Retry logic with exponential backoff.

This module provides retry decorators and utilities for handling
transient failures with exponential backoff.
"""

import asyncio
import functools
from typing import Callable, TypeVar

T = TypeVar("T")


def exponential_backoff(
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    max_retries: int = 3,
):
    """Decorator for retrying async functions with exponential backoff.

    Args:
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        multiplier: Backoff multiplier (default: 2.0)
        max_retries: Maximum number of retries (default: 3)

    Example:
        >>> @exponential_backoff(max_retries=3)
        ... async def fetch_data():
        ...     # May fail transiently
        ...     return await http_client.get(url)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt < max_retries:
                        await asyncio.sleep(delay)
                        delay = min(delay * multiplier, max_delay)
                    else:
                        raise

            # Should never reach here, but satisfy type checker
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    max_retries: int = 3,
    **kwargs,
) -> T:
    """Retry a function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        multiplier: Backoff multiplier
        max_retries: Maximum number of retries
        **kwargs: Keyword arguments for func

    Returns:
        Result from func

    Raises:
        Last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay = min(delay * multiplier, max_delay)
            else:
                raise

    # Should never reach here
    if last_exception:
        raise last_exception
