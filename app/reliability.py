from collections.abc import Callable
from typing import ParamSpec, TypeVar

import httpx
from qdrant_client.http.exceptions import ResponseHandlingException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


P = ParamSpec("P")
R = TypeVar("R")

TRANSIENT_READ_ERRORS = (
    TimeoutError,
    ConnectionError,
    httpx.TimeoutException,
    httpx.ConnectError,
    ResponseHandlingException,
)


def retry_transient_read(
    attempts: int,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """仅为无副作用的外部读取重试瞬时网络错误。"""

    return retry(
        retry=retry_if_exception_type(TRANSIENT_READ_ERRORS),
        stop=stop_after_attempt(max(1, attempts)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        reraise=True,
    )
