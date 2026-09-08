"""Privacy-bounded normalization of observable tool telemetry."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

DEFAULT_FAMILY_MAP = MappingProxyType(
    {
        "search": "discover",
        "read_document": "inspect",
        "list_sources": "inspect",
        "list_workflows": "inspect",
        "list_flows": "inspect",
        "inspect_flow": "inspect",
        "list_workflow_observations": "inspect",
        "inspect_workflow_observation": "inspect",
        "list_product_surfaces": "inspect",
        "list_connector_types": "inspect",
        "list_tasks": "inspect",
        "list_answers": "inspect",
        "tag_document": "change",
        "untag_document": "change",
        "create_task": "change",
        "approve_answer": "approve",
        "sync_source": "execute",
        "run_workflow": "execute",
        "navigate": "navigate",
    }
)


@dataclass(frozen=True, slots=True)
class TrajectoryStep:
    ordinal: int
    tool: str
    action_family: str
    arguments: Mapping[str, str | int | float | bool | None] = field(
        default_factory=dict
    )
    summary: str = ""
    ok: bool | None = None
    event_id: str = ""
    parent_id: str = ""
    started_at: float | None = None
    ended_at: float | None = None
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0

    @property
    def duration(self) -> float:
        if self.started_at is None or self.ended_at is None:
            return 0.0
        return max(0.0, self.ended_at - self.started_at)

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.cached_input_tokens + self.output_tokens


def _safe_arguments(value: Any) -> Mapping[str, str | int | float | bool | None]:
    if not isinstance(value, dict):
        return MappingProxyType({})
    output: dict[str, str | int | float | bool | None] = {}
    for key, item in value.items():
        clean_key = re.sub(r"[^a-zA-Z0-9_-]", "", str(key))[:40]
        if not clean_key or any(
            word in clean_key.casefold()
            for word in ("body", "content", "token", "secret", "password", "key")
        ):
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            output[clean_key] = item[:160] if isinstance(item, str) else item
    return MappingProxyType(output)


def normalize_steps(
    events: Iterable[Mapping[str, Any]],
    *,
    family_map: Mapping[str, str] = DEFAULT_FAMILY_MAP,
) -> tuple[TrajectoryStep, ...]:
    output: list[TrajectoryStep] = []
    for ordinal, event in enumerate(events):
        tool = (
            re.sub(r"[^a-z0-9_-]", "", str(event.get("name") or "unknown").casefold())[
                :60
            ]
            or "unknown"
        )
        output.append(
            TrajectoryStep(
                ordinal,
                tool,
                family_map.get(tool, "other"),
                _safe_arguments(event.get("args")),
                str(event.get("summary") or "")[:300],
                event.get("ok") if isinstance(event.get("ok"), bool) else None,
                str(event.get("event_id") or event.get("id") or "")[:160],
                str(event.get("parent_id") or "")[:160],
                _optional_number(event.get("started_at")),
                _optional_number(event.get("ended_at")),
                _non_negative_int(event.get("input_tokens")),
                _non_negative_int(event.get("cached_input_tokens")),
                _non_negative_int(event.get("output_tokens")),
                _non_negative_number(event.get("cost")),
            )
        )
    return tuple(output)


def _optional_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if result == result and abs(result) != float("inf") else None


def _non_negative_number(value: Any) -> float:
    result = _optional_number(value)
    return result if result is not None and result >= 0 else 0.0


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return result if result >= 0 else 0
