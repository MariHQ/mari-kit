"""Loss-bounded GenAI trace normalization and structural integrity checks."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, cast

from mari_components.json import freeze_json_mapping

from .normalize import normalize_steps
from .process import TrajectoryRun


class TraceEventKind(StrEnum):
    MODEL = "model"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    MEMORY = "memory"
    AGENT = "agent"
    EVALUATION = "evaluation"
    OTHER = "other"


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceLink:
    trace_id: str
    span_id: str
    attributes: Mapping[str, str | int | float | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.span_id.strip():
            raise ValueError("trace link span ID is required")
        object.__setattr__(self, "attributes", freeze_json_mapping(self.attributes))


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceEvent:
    event_id: str
    trace_id: str
    parent_id: str
    kind: TraceEventKind
    name: str
    outcome: bool | None
    started_at: float | None
    ended_at: float | None
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    links: tuple[TraceLink, ...] = ()
    attributes: Mapping[str, str | int | float | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.name.strip():
            raise ValueError("trace event identity and name are required")
        object.__setattr__(self, "links", tuple(self.links))
        object.__setattr__(self, "attributes", freeze_json_mapping(self.attributes))

    @property
    def duration(self) -> float:
        if self.started_at is None or self.ended_at is None:
            return 0.0
        return max(0.0, self.ended_at - self.started_at)


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedTrace:
    trace_id: str
    schema_url: str
    events: tuple[TraceEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))


class TraceIntegrityCode(StrEnum):
    DUPLICATE_EVENT_ID = "duplicate_event_id"
    MISSING_PARENT = "missing_parent"
    PARENT_CYCLE = "parent_cycle"
    NEGATIVE_DURATION = "negative_duration"
    CROSS_TRACE_PARENT = "cross_trace_parent"
    MISSING_SCHEMA = "missing_schema"


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceIntegrityIssue:
    code: TraceIntegrityCode
    event_id: str = ""
    related_id: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceIntegrityReport:
    event_count: int
    issues: tuple[TraceIntegrityIssue, ...]
    roots: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def normalize_genai_trace(
    payload: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    *,
    schema_url: str | None = None,
    maximum_events: int = 20_000,
) -> NormalizedTrace:
    """Normalize OTLP JSON or a span iterable without retaining captured content."""

    if maximum_events < 1:
        raise ValueError("maximum_events must be positive")
    spans, discovered_schema = _extract_spans(payload)
    if len(spans) > maximum_events:
        raise ValueError("trace exceeds maximum_events")
    events: list[TraceEvent] = []
    for index, span in enumerate(spans):
        attributes = _attributes(span.get("attributes"))
        event_id = str(span.get("spanId") or span.get("span_id") or f"event-{index}")
        trace_id = str(span.get("traceId") or span.get("trace_id") or "")
        parent_id = str(span.get("parentSpanId") or span.get("parent_span_id") or "")
        operation = str(attributes.get("gen_ai.operation.name") or "")
        tool_name = str(attributes.get("gen_ai.tool.name") or "")
        name = tool_name or operation or str(span.get("name") or "unknown")
        status: object = span.get("status")
        if isinstance(status, Mapping):
            status = status.get("code")
        events.append(
            TraceEvent(
                event_id=event_id[:160],
                trace_id=trace_id[:160],
                parent_id=parent_id[:160],
                kind=_event_kind(operation, attributes, tool_name),
                name=name[:160],
                outcome=_outcome(status),
                started_at=_timestamp(span, "start"),
                ended_at=_timestamp(span, "end"),
                input_tokens=_count(attributes.get("gen_ai.usage.input_tokens")),
                cached_input_tokens=_count(
                    attributes.get("gen_ai.usage.cached_input_tokens")
                ),
                output_tokens=_count(attributes.get("gen_ai.usage.output_tokens")),
                cost=_number(attributes.get("gen_ai.usage.cost")),
                links=_links(span.get("links")),
                attributes=_safe_attributes(attributes),
            )
        )
    events.sort(
        key=lambda event: (
            event.started_at is None,
            event.started_at or 0.0,
            event.event_id,
        )
    )
    trace_ids = sorted({event.trace_id for event in events if event.trace_id})
    return NormalizedTrace(
        trace_id=trace_ids[0] if len(trace_ids) == 1 else "",
        schema_url=(schema_url or discovered_schema or "")[:300],
        events=tuple(events),
    )


def inspect_trace_integrity(trace: NormalizedTrace) -> TraceIntegrityReport:
    """Report structural defects without repairing or discarding trace events."""

    issues: list[TraceIntegrityIssue] = []
    counts: dict[str, int] = {}
    for event in trace.events:
        counts[event.event_id] = counts.get(event.event_id, 0) + 1
    for event_id, count in sorted(counts.items()):
        if count > 1:
            issues.append(
                TraceIntegrityIssue(
                    code=TraceIntegrityCode.DUPLICATE_EVENT_ID, event_id=event_id
                )
            )
    by_id = {event.event_id: event for event in trace.events}
    for event in trace.events:
        if event.started_at is not None and event.ended_at is not None:
            if event.ended_at < event.started_at:
                issues.append(
                    TraceIntegrityIssue(
                        code=TraceIntegrityCode.NEGATIVE_DURATION,
                        event_id=event.event_id,
                    )
                )
        if event.parent_id and event.parent_id not in by_id:
            issues.append(
                TraceIntegrityIssue(
                    code=TraceIntegrityCode.MISSING_PARENT,
                    event_id=event.event_id,
                    related_id=event.parent_id,
                )
            )
        elif event.parent_id:
            parent = by_id[event.parent_id]
            if event.trace_id and parent.trace_id and event.trace_id != parent.trace_id:
                issues.append(
                    TraceIntegrityIssue(
                        code=TraceIntegrityCode.CROSS_TRACE_PARENT,
                        event_id=event.event_id,
                        related_id=event.parent_id,
                    )
                )
    for event in trace.events:
        seen: set[str] = set()
        current = event
        while current.parent_id in by_id:
            if current.event_id in seen:
                issues.append(
                    TraceIntegrityIssue(
                        code=TraceIntegrityCode.PARENT_CYCLE,
                        event_id=event.event_id,
                    )
                )
                break
            seen.add(current.event_id)
            current = by_id[current.parent_id]
    if not trace.schema_url:
        issues.append(TraceIntegrityIssue(code=TraceIntegrityCode.MISSING_SCHEMA))
    unique = {(issue.code, issue.event_id, issue.related_id): issue for issue in issues}
    roots = tuple(
        event.event_id
        for event in trace.events
        if not event.parent_id or event.parent_id not in by_id
    )
    return TraceIntegrityReport(
        event_count=len(trace.events),
        issues=tuple(
            unique[key] for key in sorted(unique, key=lambda row: tuple(map(str, row)))
        ),
        roots=roots,
    )


def project_tool_trajectory(
    trace: NormalizedTrace,
    *,
    trajectory_id: str | None = None,
    outcome: str = "unknown",
) -> TrajectoryRun:
    """Project tool spans into Mari's smaller trajectory representation."""

    events = [
        {
            "name": event.name,
            "ok": event.outcome,
            "event_id": event.event_id,
            "parent_id": event.parent_id,
            "started_at": event.started_at,
            "ended_at": event.ended_at,
            "input_tokens": event.input_tokens,
            "cached_input_tokens": event.cached_input_tokens,
            "output_tokens": event.output_tokens,
            "cost": event.cost,
        }
        for event in trace.events
        if event.kind is TraceEventKind.TOOL
    ]
    identifier = trajectory_id or trace.trace_id
    if not identifier:
        raise ValueError("trajectory_id is required when the trace has no single ID")
    return TrajectoryRun(
        trajectory_id=identifier, steps=normalize_steps(events), outcome=outcome
    )


def _extract_spans(
    payload: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], str]:
    if not isinstance(payload, Mapping):
        return list(payload), ""
    root = cast(Mapping[str, Any], payload)
    spans: list[Mapping[str, Any]] = []
    schemas: list[str] = []
    resources = _mapping_list(root, "resourceSpans", "resource_spans")
    for resource in resources:
        if not isinstance(resource, Mapping):
            continue
        for scope in _mapping_list(resource, "scopeSpans", "scope_spans"):
            if not isinstance(scope, Mapping):
                continue
            schema = str(scope.get("schemaUrl") or scope.get("schema_url") or "")
            if schema:
                schemas.append(schema)
            spans.extend(_mapping_list(scope, "spans"))
    if spans:
        return spans, schemas[0] if len(set(schemas)) == 1 else ""
    direct = _mapping_list(root, "spans")
    if direct:
        return direct, ""
    return [root], ""


def _mapping_list(value: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, list):
            return [
                cast(Mapping[str, Any], item)
                for item in candidate
                if isinstance(item, Mapping)
            ]
    return []


def _attributes(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    output: dict[str, Any] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, Mapping) or not isinstance(item.get("key"), str):
                continue
            raw = item.get("value")
            if isinstance(raw, Mapping):
                raw = next(iter(raw.values()), None)
            output[item["key"]] = raw
    return output


def _safe_attributes(
    values: Mapping[str, Any],
) -> Mapping[str, str | int | float | bool]:
    output: dict[str, str | int | float | bool] = {}
    for key, value in values.items():
        folded = key.casefold()
        if any(
            word in folded
            for word in ("content", "message", "prompt", "result", "arguments")
        ):
            continue
        if not (key.startswith("gen_ai.") or key.startswith("error.")):
            continue
        if isinstance(value, (str, int, float, bool)) and not (
            isinstance(value, float) and not math.isfinite(value)
        ):
            output[key[:160]] = value[:300] if isinstance(value, str) else value
    return output


def _event_kind(
    operation: str, attrs: Mapping[str, Any], tool_name: str
) -> TraceEventKind:
    value = operation.casefold()
    if tool_name or "tool" in value:
        return TraceEventKind.TOOL
    if "retriev" in value or "gen_ai.retrieval.query" in attrs:
        return TraceEventKind.RETRIEVAL
    if "memory" in value:
        return TraceEventKind.MEMORY
    if "agent" in value:
        return TraceEventKind.AGENT
    if "evaluat" in value:
        return TraceEventKind.EVALUATION
    if value in {"chat", "generate_content", "text_completion", "embeddings"}:
        return TraceEventKind.MODEL
    return TraceEventKind.OTHER


def _links(value: object) -> tuple[TraceLink, ...]:
    output: list[TraceLink] = []
    if not isinstance(value, list):
        return ()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        context = item.get("spanContext", item.get("context", item))
        if not isinstance(context, Mapping):
            continue
        span_id = str(context.get("spanId") or context.get("span_id") or "")
        if not span_id:
            continue
        output.append(
            TraceLink(
                trace_id=str(context.get("traceId") or context.get("trace_id") or "")[
                    :160
                ],
                span_id=span_id[:160],
                attributes=_safe_attributes(_attributes(item.get("attributes"))),
            )
        )
    return tuple(output)


def _timestamp(span: Mapping[str, Any], prefix: str) -> float | None:
    for key in (f"{prefix}TimeUnixNano", f"{prefix}_time_unix_nano", f"{prefix}_time"):
        if key not in span:
            continue
        try:
            value = float(span[key])
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        return value / 1_000_000_000 if "nano" in key.casefold() else value
    return None


def _outcome(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return True if value == 1 else False if value == 2 else None
    status = str(value or "").casefold()
    if status in {"ok", "success", "status_code_ok"}:
        return True
    if status in {"error", "failed", "failure", "status_code_error"}:
        return False
    return None


def _count(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if not isinstance(value, (str, int, float)):
        return 0
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, result)


def _number(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if not isinstance(value, (str, int, float)):
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) and result >= 0 else 0.0
