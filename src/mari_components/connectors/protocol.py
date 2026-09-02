"""Connector error and validation functions without runtime orchestration."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, TypeVar, runtime_checkable

from mari_components.errors import (
    AuthenticationFailure,
    PermanentFailure,
    TransientFailure,
)
from mari_components.http import HttpTransport
from mari_components.types import ChangeHint, PollPage, PollRequest


class ErrorKind(StrEnum):
    AUTH = "auth"
    TRANSIENT = "transient"
    PERMANENT = "permanent"


class ConnectorMode(StrEnum):
    """How a connector learns that provider state may have changed."""

    POLL = "poll"
    STREAM = "stream"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    message: str = ""
    identity: str = ""


def classify_error(error: BaseException) -> ErrorKind:
    if isinstance(error, AuthenticationFailure):
        return ErrorKind.AUTH
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
        return ErrorKind.TRANSIENT
    if status in (401, 403) or any(
        value in text for value in ("unauthorized", "forbidden", "invalid token")
    ):
        return ErrorKind.AUTH
    if (
        status in (408, 425)
        or status >= 500
        or isinstance(error, (ConnectionError, TimeoutError))
    ):
        return ErrorKind.TRANSIENT
    if any(
        value in text
        for value in (
            "timeout",
            "timed out",
            "unreachable",
            "network error",
            "temporarily unavailable",
        )
    ):
        return ErrorKind.TRANSIENT
    return ErrorKind.PERMANENT


T = TypeVar("T")
ConfigT = TypeVar("ConfigT", contravariant=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamEvent:
    """One raw delivery received from an application-owned webhook or stream."""

    provider: str
    raw_body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)
    event_type: str = ""

    def __post_init__(self) -> None:
        provider = self.provider.strip().casefold()
        if not provider:
            raise ValueError("stream event provider is required")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "raw_body", bytes(self.raw_body))
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


VerifyStreamEvent = Callable[[StreamEvent], None]


@runtime_checkable
class PollingConnector(Protocol[ConfigT]):
    """A cursor/checkpoint connector that enumerates canonical provider state."""

    def __call__(
        self,
        config: ConfigT,
        request: PollRequest,
        *,
        http: HttpTransport,
    ) -> Iterator[PollPage]: ...


@runtime_checkable
class StreamingConnector(Protocol):
    """A verified provider-event parser that emits a bounded change hint."""

    def __call__(
        self,
        event: StreamEvent,
        *,
        verify: VerifyStreamEvent,
        maximum_bytes: int = 1_048_576,
    ) -> ChangeHint: ...


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
            if kind is not ErrorKind.TRANSIENT or attempt + 1 >= attempts:
                raise
            requested = getattr(error, "retry_after", None)
            delay = float(requested) if requested is not None else min(2**attempt, 8)
            sleep(max(0.0, min(delay, maximum_delay)))
    raise AssertionError("retry loop exited without a result")
