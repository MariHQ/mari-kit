"""Declarative, bounded batch ingestion for JSON REST collections."""

from __future__ import annotations

import urllib.parse
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from mari_components.connectors._shared import json_response
from mari_components.errors import PermanentFailure
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import KnowledgeDocument, PollPage, PollRequest

JSONDocument = Callable[[Mapping[str, Any]], KnowledgeDocument | None]


@dataclass(frozen=True, slots=True, kw_only=True)
class JSONAPIConfig:
    url: str
    records_path: tuple[str, ...] = ("items",)
    next_path: tuple[str, ...] = ("next",)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    page_size_parameter: str = ""

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("JSON API URL must use HTTP or HTTPS")
        if not self.records_path:
            raise ValueError("JSON API records_path is required")
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


def _at_path(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _with_page_size(url: str, parameter: str, size: int) -> str:
    if not parameter:
        return url
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key == parameter for key, _value in query):
        query.append((parameter, str(size)))
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(query),
            parsed.fragment,
        )
    )


def _continuation(origin: str, value: str) -> str:
    url = urllib.parse.urljoin(origin, value)
    expected = urllib.parse.urlsplit(origin)
    observed = urllib.parse.urlsplit(url)
    if (observed.scheme, observed.netloc) != (expected.scheme, expected.netloc):
        raise PermanentFailure("JSON API continuation escaped the configured origin")
    return url


def poll_json_api(
    config: JSONAPIConfig,
    request: PollRequest,
    *,
    http: HttpTransport,
    document: JSONDocument,
) -> Iterator[PollPage]:
    """Normalize a same-origin JSON collection using an injected row mapper."""

    url = _continuation(config.url, request.checkpoint or config.url)
    for _ in range(request.page_limit):
        value = json_response(
            http,
            HttpRequest(
                "GET",
                _with_page_size(url, config.page_size_parameter, request.page_size),
                config.headers,
            ),
        )
        records = _at_path(value, config.records_path)
        if not isinstance(records, list):
            raise PermanentFailure("JSON API records path did not resolve to a list")
        if len(records) > request.page_size:
            raise PermanentFailure(
                "JSON API returned more than the requested page size"
            )
        documents = tuple(
            selected
            for row in records
            if isinstance(row, dict) and (selected := document(row)) is not None
        )
        raw_next = _at_path(value, config.next_path) if config.next_path else None
        next_url = _continuation(config.url, str(raw_next)) if raw_next else ""
        complete = not next_url
        yield PollPage(
            upserts=documents,
            next_cursor=request.cursor,
            next_checkpoint=None if complete else next_url,
            snapshot_complete=complete,
        )
        if complete:
            return
        if next_url == url:
            raise PermanentFailure("JSON API returned a repeated continuation")
        url = next_url
    yield PollPage(
        next_cursor=request.cursor,
        next_checkpoint=url,
        snapshot_complete=False,
        provider_metadata={"reason": "page_limit"},
    )
