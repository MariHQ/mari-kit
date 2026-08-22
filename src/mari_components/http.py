"""Minimal injected HTTP boundary shared by connector functions."""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

_SENSITIVE_HEADERS = frozenset({"authorization", "proxy-authorization", "x-api-key"})
_SENSITIVE_QUERY = frozenset({"access_token", "api_key", "apikey", "key", "token"})


def _redacted_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    netloc = re.sub(r"^[^@]+@", "[REDACTED]@", parsed.netloc)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe_query = urllib.parse.urlencode(
        [
            (key, "[REDACTED]" if key.casefold() in _SENSITIVE_QUERY else item)
            for key, item in query
        ]
    )
    return urllib.parse.urlunsplit(
        (parsed.scheme, netloc, parsed.path, safe_query, parsed.fragment)
    )


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if not self.method.strip() or not self.url.strip() or self.timeout <= 0:
            raise ValueError("HTTP method, URL, and positive timeout are required")
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))

    def __repr__(self) -> str:
        headers = {
            key: ("[REDACTED]" if key.casefold() in _SENSITIVE_HEADERS else value)
            for key, value in self.headers.items()
        }
        body = "[REDACTED]" if self.body is not None else None
        return (
            f"HttpRequest(method={self.method!r}, url={_redacted_url(self.url)!r}, "
            f"headers={headers!r}, body={body!r}, timeout={self.timeout!r})"
        )


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes

    def __post_init__(self) -> None:
        if not 100 <= self.status <= 599:
            raise ValueError("HTTP status must be between 100 and 599")
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


HttpTransport = Callable[[HttpRequest], HttpResponse]
