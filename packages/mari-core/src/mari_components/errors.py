"""Typed failures which hosts can retry, display, or reject explicitly."""

from __future__ import annotations


class ComponentError(RuntimeError):
    """Base class for failures intentionally exposed by this package."""


class AuthenticationFailure(ComponentError):
    """Provider credentials are absent, invalid, expired, or unauthorized."""


class RateLimitFailure(ComponentError):
    """A provider rejected work due to a quota or rate limit."""

    def __init__(self, message: str, *, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class TransientFailure(ComponentError):
    """A bounded retry may succeed without changing caller input."""


class PermanentFailure(ComponentError):
    """The operation cannot succeed without changing caller input or code."""


class MalformedModelOutput(ComponentError):
    """A model response did not satisfy the recipe's explicit output contract."""


class IncompleteSnapshot(ComponentError):
    """A provider result cannot be treated as an authoritative full snapshot."""
