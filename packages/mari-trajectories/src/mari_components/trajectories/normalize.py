"""Privacy-bounded normalization of observable tool telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping


DEFAULT_FAMILY_MAP = MappingProxyType({
    "search": "discover", "read_document": "inspect", "list_sources": "inspect",
    "list_workflows": "inspect", "list_flows": "inspect", "inspect_flow": "inspect",
    "list_workflow_observations": "inspect", "inspect_workflow_observation": "inspect",
    "list_product_surfaces": "inspect", "list_connector_types": "inspect",
    "list_tasks": "inspect", "list_answers": "inspect",
    "tag_document": "change", "untag_document": "change", "create_task": "change",
    "approve_answer": "approve", "sync_source": "execute", "run_workflow": "execute",
    "navigate": "navigate",
})


@dataclass(frozen=True, slots=True)
class TrajectoryStep:
    ordinal: int
    tool: str
    action_family: str
    arguments: Mapping[str, str | int | float | bool | None] = field(default_factory=dict)
    summary: str = ""
    ok: bool = False


def _safe_arguments(value: Any) -> Mapping[str, str | int | float | bool | None]:
    if not isinstance(value, dict):
        return MappingProxyType({})
    output: dict[str, str | int | float | bool | None] = {}
    for key, item in value.items():
        clean_key = re.sub(r"[^a-zA-Z0-9_-]", "", str(key))[:40]
        if not clean_key or any(word in clean_key.casefold() for word in ("body", "content", "token", "secret", "password", "key")):
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            output[clean_key] = item[:160] if isinstance(item, str) else item
    return MappingProxyType(output)


def normalize_steps(events: Iterable[Mapping[str, Any]], *, family_map: Mapping[str, str] = DEFAULT_FAMILY_MAP) -> tuple[TrajectoryStep, ...]:
    output: list[TrajectoryStep] = []
    for ordinal, event in enumerate(events):
        tool = re.sub(r"[^a-z0-9_-]", "", str(event.get("name") or "unknown").casefold())[:60] or "unknown"
        output.append(TrajectoryStep(ordinal, tool, family_map.get(tool, "other"), _safe_arguments(event.get("args")), str(event.get("summary") or "")[:300], bool(event.get("ok"))))
    return tuple(output)
