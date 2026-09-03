"""Verified event ingestion and canonical refetch for streaming connectors."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any

from mari_components.types import ChangeHint, PollPage

from .events import (
    box_change_hint,
    cloudevent_change_hint,
    coalesce_hints,
    confluence_change_hint,
    gdrive_change_hint,
    github_change_hint,
    gitlab_change_hint,
    microsoft_graph_change_hint,
    object_storage_change_hint,
    parse_json_object,
    slack_change_hint,
)
from .protocol import StreamEvent, VerifyStreamEvent

HydrateChange = Callable[[ChangeHint], Iterable[PollPage]]


def stream_change_hint(
    event: StreamEvent,
    *,
    verify: VerifyStreamEvent,
    maximum_bytes: int = 1_048_576,
) -> ChangeHint:
    """Verify one delivery, then reduce it to a provider-neutral change hint."""
    verify(event)
    if event.provider == "gdrive":
        return gdrive_change_hint(event.headers)
    payload: Mapping[str, Any] = parse_json_object(
        event.raw_body, maximum_bytes=maximum_bytes
    )
    if event.provider == "github":
        event_type = event.event_type or _header(event.headers, "x-github-event")
        return github_change_hint(event_type, payload)
    if event.provider == "slack":
        return slack_change_hint(payload)
    if event.provider == "confluence":
        return confluence_change_hint(payload)
    if event.provider == "gitlab":
        return gitlab_change_hint(payload)
    if event.provider == "box":
        return box_change_hint(payload)
    if event.provider in {"onedrive", "sharepoint"}:
        return microsoft_graph_change_hint(payload, provider=event.provider)
    if event.provider in {"s3", "gcs", "azure_blob"}:
        return object_storage_change_hint(payload, provider=event.provider)
    if event.provider == "cloudevents":
        return cloudevent_change_hint(payload)
    raise ValueError(f"unsupported streaming provider: {event.provider!r}")


def stream_hints(
    events: Iterable[StreamEvent],
    *,
    verify: VerifyStreamEvent,
    maximum_events: int = 500,
    maximum_bytes: int = 1_048_576,
) -> Iterator[ChangeHint]:
    """Emit coalesced change hints without owning a cursor or checkpoint."""

    if maximum_events < 1:
        raise ValueError("maximum_events must be positive")
    hints: list[ChangeHint] = []
    for index, event in enumerate(events):
        if index >= maximum_events:
            raise ValueError("stream batch exceeds maximum_events")
        hints.append(
            stream_change_hint(event, verify=verify, maximum_bytes=maximum_bytes)
        )
    yield from coalesce_hints(hints)


def stream_pages(
    events: Iterable[StreamEvent],
    *,
    verify: VerifyStreamEvent,
    hydrate: HydrateChange,
    maximum_events: int = 500,
    maximum_bytes: int = 1_048_576,
) -> Iterator[PollPage]:
    """Verify, bound, coalesce, and hydrate streaming events.

    Events are hints, never authoritative document bodies. ``hydrate`` must
    refetch canonical provider state and return ordinary ``PollPage`` values so
    polling and streaming share the same synchronization planner.
    """
    if maximum_events < 1:
        raise ValueError("maximum_events must be positive")
    for hint in stream_hints(
        events,
        verify=verify,
        maximum_events=maximum_events,
        maximum_bytes=maximum_bytes,
    ):
        yield from hydrate(hint)


def hydrate_hints(
    hints: Iterable[ChangeHint], *, hydrate: HydrateChange
) -> Iterator[PollPage]:
    """Hydrate already-verified/coalesced hints into canonical polling pages."""

    for hint in coalesce_hints(list(hints)):
        yield from hydrate(hint)


def _header(headers: Mapping[str, str], name: str) -> str:
    target = name.casefold()
    return next(
        (value.strip() for key, value in headers.items() if key.casefold() == target),
        "",
    )
