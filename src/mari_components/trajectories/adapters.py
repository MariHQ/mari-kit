"""Small adapters from common trace exports into normalized trajectory steps."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .normalize import TrajectoryStep, normalize_steps


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryAdapterIssue:
    code: str
    record_index: int
    detail: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryAdapterResult:
    source_format: str
    steps: tuple[TrajectoryStep, ...]
    issues: tuple[TrajectoryAdapterIssue, ...]
    dropped_records: int = 0


def _arguments(
    value: object,
    *,
    index: int,
    issues: list[TrajectoryAdapterIssue],
) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            issues.append(
                TrajectoryAdapterIssue(
                    code="invalid_tool_arguments", record_index=index
                )
            )
            return {}
        if isinstance(parsed, dict):
            return parsed
    if value not in (None, "", {}):
        issues.append(
            TrajectoryAdapterIssue(code="non_object_tool_arguments", record_index=index)
        )
    return {}


def _bounded(
    records: Iterable[Mapping[str, Any]], maximum_events: int
) -> tuple[Mapping[str, Any], ...]:
    if maximum_events < 1:
        raise ValueError("maximum_events must be positive")
    values = tuple(records)
    if len(values) > maximum_events:
        raise ValueError("trajectory exceeds maximum_events")
    return values


def normalize_openai_trajectory(
    records: Iterable[Mapping[str, Any]],
    *,
    maximum_events: int = 10_000,
) -> TrajectoryAdapterResult:
    """Normalize Chat Completions messages or Responses API event items.

    Tool-result content is not retained. A result is successful only when the
    export contains an explicit success status; ordinary tool messages remain
    unknown because their content has no portable success semantics.
    """

    values = _bounded(records, maximum_events)
    issues: list[TrajectoryAdapterIssue] = []
    outcomes: dict[str, bool | None] = {}
    for record in values:
        call_id = str(record.get("tool_call_id") or record.get("call_id") or "")
        if record.get("role") == "tool" or record.get("type") == "function_call_output":
            outcomes[call_id] = _explicit_outcome(record.get("status"))
    events: list[dict[str, Any]] = []
    dropped = 0
    for index, record in enumerate(values):
        if record.get("type") == "function_call":
            call_id = str(record.get("call_id") or record.get("id") or "")
            events.append(
                {
                    "name": record.get("name"),
                    "args": _arguments(
                        record.get("arguments"), index=index, issues=issues
                    ),
                    # Responses ``function_call.status=completed`` means the
                    # arguments finished streaming, not that the tool worked.
                    "ok": outcomes.get(call_id),
                    "event_id": call_id,
                    "parent_id": record.get("response_id") or "",
                }
            )
            continue
        calls = record.get("tool_calls")
        if record.get("role") == "assistant" and isinstance(calls, list):
            for call in calls:
                if not isinstance(call, Mapping):
                    issues.append(
                        TrajectoryAdapterIssue(
                            code="invalid_tool_call", record_index=index
                        )
                    )
                    continue
                function = call.get("function")
                function = function if isinstance(function, Mapping) else {}
                call_id = str(call.get("id") or "")
                events.append(
                    {
                        "name": function.get("name") or call.get("name"),
                        "args": _arguments(
                            function.get("arguments", call.get("arguments")),
                            index=index,
                            issues=issues,
                        ),
                        "ok": outcomes.get(call_id),
                        "event_id": call_id,
                        "parent_id": record.get("id") or "",
                    }
                )
            continue
        dropped += 1
    _check_emitted_limit(events, maximum_events)
    return TrajectoryAdapterResult(
        source_format="openai",
        steps=normalize_steps(events),
        issues=tuple(issues),
        dropped_records=dropped,
    )


def normalize_anthropic_trajectory(
    messages: Iterable[Mapping[str, Any]],
    *,
    maximum_events: int = 10_000,
) -> TrajectoryAdapterResult:
    """Normalize Anthropic ``tool_use`` and ``tool_result`` content blocks."""

    values = _bounded(messages, maximum_events)
    issues: list[TrajectoryAdapterIssue] = []
    outcomes: dict[str, bool | None] = {}
    for message in values:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, Mapping) and block.get("type") == "tool_result":
                outcomes[str(block.get("tool_use_id") or "")] = (
                    not block["is_error"]
                    if isinstance(block.get("is_error"), bool)
                    else None
                )
    events: list[dict[str, Any]] = []
    dropped = 0
    for index, message in enumerate(values):
        content = message.get("content")
        if not isinstance(content, list):
            dropped += 1
            continue
        found = False
        for block in content:
            if not isinstance(block, Mapping) or block.get("type") != "tool_use":
                continue
            found = True
            call_id = str(block.get("id") or "")
            events.append(
                {
                    "name": block.get("name"),
                    "args": _arguments(block.get("input"), index=index, issues=issues),
                    "ok": outcomes.get(call_id),
                    "event_id": call_id,
                    "parent_id": message.get("id") or "",
                }
            )
        if not found:
            dropped += 1
    _check_emitted_limit(events, maximum_events)
    return TrajectoryAdapterResult(
        source_format="anthropic",
        steps=normalize_steps(events),
        issues=tuple(issues),
        dropped_records=dropped,
    )


def normalize_otel_trajectory(
    spans: Iterable[Mapping[str, Any]],
    *,
    maximum_events: int = 10_000,
) -> TrajectoryAdapterResult:
    """Normalize tool spans using OpenTelemetry GenAI attribute spellings."""

    values = _bounded(spans, maximum_events)
    issues: list[TrajectoryAdapterIssue] = []
    events: list[dict[str, Any]] = []
    dropped = 0
    ordered = sorted(
        enumerate(values), key=lambda pair: (_timestamp(pair[1], "start"), pair[0])
    )
    for index, span in ordered:
        attrs = _otel_attributes(span.get("attributes"))
        name = _first(attrs, "gen_ai.tool.name", "tool.name", "tool_name")
        if not name:
            issues.append(
                TrajectoryAdapterIssue(code="non_tool_span", record_index=index)
            )
            dropped += 1
            continue
        status = span.get("status")
        if isinstance(status, Mapping):
            status = status.get("code")
        events.append(
            {
                "name": name,
                "args": _arguments(
                    _first(
                        attrs,
                        "gen_ai.tool.call.arguments",
                        "tool.arguments",
                        "tool_args",
                    ),
                    index=index,
                    issues=issues,
                ),
                "ok": _explicit_outcome(status),
                "event_id": span.get("span_id") or span.get("spanId") or "",
                "parent_id": span.get("parent_span_id")
                or span.get("parentSpanId")
                or "",
                "started_at": _timestamp(span, "start"),
                "ended_at": _timestamp(span, "end"),
                "input_tokens": _first(
                    attrs, "gen_ai.usage.input_tokens", "input_tokens"
                )
                or 0,
                "cached_input_tokens": _first(
                    attrs, "gen_ai.usage.cached_input_tokens", "cached_input_tokens"
                )
                or 0,
                "output_tokens": _first(
                    attrs, "gen_ai.usage.output_tokens", "output_tokens"
                )
                or 0,
                "cost": _first(attrs, "gen_ai.usage.cost", "cost") or 0.0,
            }
        )
    _check_emitted_limit(events, maximum_events)
    return TrajectoryAdapterResult(
        source_format="otel-genai",
        steps=normalize_steps(events),
        issues=tuple(issues),
        dropped_records=dropped,
    )


def _first(values: Mapping[str, Any], *keys: str) -> Any:
    return next((values[key] for key in keys if key in values), None)


def _otel_attributes(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, list):
        return {}
    output: dict[str, Any] = {}
    for item in value:
        if not isinstance(item, Mapping) or not isinstance(item.get("key"), str):
            continue
        raw = item.get("value")
        if isinstance(raw, Mapping):
            raw = next(
                (
                    raw[key]
                    for key in (
                        "stringValue",
                        "intValue",
                        "doubleValue",
                        "boolValue",
                        "string_value",
                        "int_value",
                        "double_value",
                        "bool_value",
                    )
                    if key in raw
                ),
                None,
            )
        output[item["key"]] = raw
    return output


def _timestamp(span: Mapping[str, Any], prefix: str) -> float:
    for key in (f"{prefix}_time", f"{prefix}TimeUnixNano", f"{prefix}_time_unix_nano"):
        value = span.get(key)
        if (
            isinstance(value, (int, float, str))
            and not isinstance(value, bool)
            and str(value).strip()
        ):
            try:
                result = float(value)
            except ValueError:
                continue
            return result / 1_000_000_000 if "nano" in key.casefold() else result
    return 0.0


def _explicit_outcome(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return True if value == 1 else False if value == 2 else None
    normalized = str(value or "").strip().casefold()
    if normalized in {
        "ok",
        "success",
        "succeeded",
        "completed",
        "unset",
        "status_code_ok",
        "status_code_unset",
    }:
        return None if normalized in {"unset", "status_code_unset"} else True
    if normalized in {
        "error",
        "failed",
        "failure",
        "cancelled",
        "timeout",
        "status_code_error",
    }:
        return False
    return None


def _check_emitted_limit(events: list[dict[str, Any]], maximum_events: int) -> None:
    if len(events) > maximum_events:
        raise ValueError("normalized trajectory exceeds maximum_events")
