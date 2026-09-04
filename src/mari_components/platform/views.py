"""Dependency-aware materialized-view refresh planning."""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from mari_components.dependencies import (
    DependencyKey,
    DependencyStamp,
    DerivationSpec,
    UpdateAction,
    dependency_fingerprint,
    materialization_receipt,
    plan_dependency_updates,
)
from mari_components.references import ObjectRef


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
        # The legacy API supplies deltas. Expand them into a complete snapshot
        # before handing off to the same planner used by atoms and artifacts.
        current = prior | {
            source: revision
            for source, revision in changed_revisions.items()
            if source in prior or fnmatch.fnmatchcase(source, view.source_pattern)
        }

        def stamps(revisions: Mapping[str, str]) -> tuple[DependencyStamp, ...]:
            return tuple(
                DependencyStamp(
                    dependency=DependencyKey(
                        object=ObjectRef(namespace="source", object_id=source),
                        aspect="revision",
                    ),
                    fingerprint=dependency_fingerprint(revision),
                )
                for source, revision in sorted(revisions.items())
            )

        before, after = stamps(prior), stamps(current)
        output = DependencyKey(
            object=ObjectRef(namespace="view", object_id=build.artifact_id)
        )
        old_spec = DerivationSpec(
            output=output,
            inputs=tuple(item.dependency for item in before),
            implementation=build.transform,
        )
        new_spec = DerivationSpec(
            output=output,
            inputs=tuple(item.dependency for item in after),
            implementation=view.transform,
        )
        plan = plan_dependency_updates(
            sources=after,
            derivations=(new_spec,),
            materializations=(
                materialization_receipt(
                    old_spec, before, output_fingerprint=dependency_fingerprint(build)
                ),
            ),
        )
        update = plan.updates[0]
        if update.action is not UpdateAction.REUSE:
            reason = (
                "transform_changed"
                if "implementation_changed" in update.reasons
                else "source_set_changed"
                if "input_set_changed" in update.reasons
                else "input_changed"
            )
            tasks.append(ViewRefreshTask(artifact_id=build.artifact_id, reason=reason))
        else:
            reused.append(build.artifact_id)
    return ViewRefreshPlan(
        view_id=view.view_id, tasks=tuple(tasks), reused_artifact_ids=tuple(reused)
    )
