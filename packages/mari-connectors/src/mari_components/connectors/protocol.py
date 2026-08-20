"""Connector error and validation functions without runtime orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Callable, TypeVar

from mari_components.errors import (
    AuthenticationFailure,
    PermanentFailure,
    RateLimitFailure,
    TransientFailure,
)


class ErrorKind(str, Enum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    PERMANENT = "permanent"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    message: str = ""
    identity: str = ""


def classify_error(error: BaseException) -> ErrorKind:
    if isinstance(error, AuthenticationFailure):
        return ErrorKind.AUTH
    if isinstance(error, RateLimitFailure):
        return ErrorKind.RATE_LIMIT
    if isinstance(error, TransientFailure):
        return ErrorKind.TRANSIENT
    if isinstance(error, PermanentFailure):
        return ErrorKind.PERMANENT
    status = int(getattr(error, "status", 0) or 0)
    text = str(error).lower()
    textual_status = re.search(r"(?:http|status)[^0-9]{0,8}([45][0-9]{2})", text)
    if not status and textual_status:
        status = int(textual_status.group(1))
    if status == 429 or "rate limit" in text or "ratelimited" in text:
        return ErrorKind.RATE_LIMIT
    if status in (401, 403) or any(
        value in text for value in ("unauthorized", "forbidden", "invalid token")
    ):
        return ErrorKind.AUTH
    if status in (408, 425) or status >= 500 or isinstance(error, (ConnectionError, TimeoutError)):
        return ErrorKind.TRANSIENT
    if any(
        value in text
        for value in ("timeout", "timed out", "unreachable", "network error", "temporarily unavailable")
    ):
        return ErrorKind.TRANSIENT
    return ErrorKind.PERMANENT


T = TypeVar("T")


def call_with_retry(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    sleep: Callable[[float], None],
    maximum_delay: float = 30.0,
) -> T:
    """Call an operation with explicit, bounded retry behavior.

    A sleep callable is required so the package never chooses a scheduler or
    blocks unexpectedly. Authentication and permanent failures are not retried.
    """
    if attempts < 1 or maximum_delay < 0:
        raise ValueError("attempts must be positive and maximum_delay non-negative")
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as error:
            kind = classify_error(error)
            if kind not in {ErrorKind.RATE_LIMIT, ErrorKind.TRANSIENT} or attempt + 1 >= attempts:
                raise
            requested = getattr(error, "retry_after", None)
            delay = float(requested) if requested is not None else min(2**attempt, 8)
            sleep(max(0.0, min(delay, maximum_delay)))
    raise AssertionError("retry loop exited without a result")
