"""Dependency-aware materialized-view refresh planning."""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterializedView:
    view_id: str
    transform: str
    source_pattern: str

    def __post_init__(self) -> None:
        if not self.view_id or not self.transform or not self.source_pattern:
            raise ValueError("view ID, transform, and source pattern are required")


@dataclass(frozen=True, slots=True, kw_only=True)
class ViewMaterialization:
    artifact_id: str
    view_id: str
    transform: str
    input_revisions: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ViewRefreshTask:
    artifact_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ViewRefreshPlan:
    view_id: str
    tasks: tuple[ViewRefreshTask, ...]
    reused_artifact_ids: tuple[str, ...]


def plan_view_refresh(
    *,
    view: MaterializedView,
    materializations: Iterable[ViewMaterialization],
    changed_revisions: Mapping[str, str],
) -> ViewRefreshPlan:
    tasks: list[ViewRefreshTask] = []
    reused: list[str] = []
    for build in sorted(materializations, key=lambda item: item.artifact_id):
        if build.view_id != view.view_id:
            continue
        prior = dict(build.input_revisions)
        transform_changed = build.transform != view.transform
        inputs_changed = any(source in prior and prior[source] != revision for source, revision in changed_revisions.items())
        source_set_changed = any(source not in prior and fnmatch.fnmatchcase(source, view.source_pattern) for source in changed_revisions)
        if transform_changed or inputs_changed or source_set_changed:
            reason = "transform_changed" if transform_changed else "source_set_changed" if source_set_changed else "input_changed"
            tasks.append(ViewRefreshTask(artifact_id=build.artifact_id, reason=reason))
        else:
            reused.append(build.artifact_id)
    return ViewRefreshPlan(view_id=view.view_id, tasks=tuple(tasks), reused_artifact_ids=tuple(reused))
