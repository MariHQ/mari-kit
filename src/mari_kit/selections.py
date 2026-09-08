"""Conservative selection dependencies, including previously unseen members."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .dependencies import (
    DependencyKey,
    DependencyStamp,
    DependencyUpdate,
    DerivationSpec,
    MaterializationReceipt,
    dependency_fingerprint,
    materialization_receipt,
    plan_dependency_updates,
)
from .json import freeze_json_mapping
from .references import ObjectRef


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectionSpec:
    """Identity and versioned rule for a scoped, ordered selection.

    The host executes the predicate/ranker. Configuration must include its query,
    thresholds, limit, and model/index versions when applicable. Candidate stamps
    cover all fields read by that rule, including eligibility observations.
    """

    object: ObjectRef
    implementation: str
    configuration: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.implementation.strip():
            raise ValueError("selection implementation version is required")
        object.__setattr__(
            self, "configuration", freeze_json_mapping(self.configuration)
        )

    @property
    def output(self) -> DependencyKey:
        return DependencyKey(object=self.object, aspect="selection_membership")


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectionPlan:
    candidates: tuple[DependencyStamp, ...]
    sources: tuple[DependencyStamp, ...]
    derivation: DerivationSpec
    update: DependencyUpdate


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectionReceipt:
    materialization: MaterializationReceipt
    selected: tuple[DependencyStamp, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected", tuple(self.selected))

    @property
    def consumer_inputs(self) -> tuple[DependencyStamp, ...]:
        """Membership plus exact consumed revisions, not the entire candidate pool."""
        return (self.materialization.output, *self.selected)


def plan_selection(
    spec: SelectionSpec,
    candidates: Iterable[DependencyStamp],
    *,
    dependencies: Iterable[DependencyStamp] = (),
    previous: SelectionReceipt | None = None,
) -> SelectionPlan:
    """Plan reevaluation against the COMPLETE current candidate partition.

    Any candidate insertion, removal, or fingerprint edit triggers reevaluation,
    even for a previous nonwinner. Semantic/top-k rules have no inferred safe
    exclusion bound. Additional stamps cover policy/query/index inputs. An empty
    partition is an explicit snapshot. This function performs no authorization.
    """
    rows = tuple(sorted(candidates, key=lambda s: s.dependency.key))
    extra = tuple(dependencies)
    if len({s.dependency for s in rows}) != len(rows):
        raise ValueError("duplicate selection candidates")
    if any(s.dependency.object.scope != spec.object.scope for s in (*rows, *extra)):
        raise ValueError("selection inputs must share its scope")
    universe = DependencyStamp(
        dependency=DependencyKey(object=spec.object, aspect="selection_candidates"),
        fingerprint=dependency_fingerprint(rows),
    )
    if any(s.dependency in (spec.output, universe.dependency) for s in rows):
        raise ValueError("selection candidates cannot use its reserved output keys")
    sources = (universe, *extra)
    derivation = DerivationSpec(
        output=spec.output,
        inputs=tuple(s.dependency for s in sources),
        implementation=spec.implementation,
        configuration=spec.configuration,
    )
    if previous is not None:
        keys = tuple(s.dependency for s in previous.selected)
        if (
            previous.materialization.output.dependency != spec.output
            or len(set(keys)) != len(keys)
            or any(key.object.scope != spec.object.scope for key in keys)
            or previous.materialization.output.fingerprint
            != dependency_fingerprint(keys)
        ):
            raise ValueError("invalid selection receipt")
    update = plan_dependency_updates(
        sources=sources,
        derivations=(derivation,),
        materializations=(previous.materialization,) if previous else (),
    ).updates[0]
    if previous is not None and not update.reasons:
        current = {s.dependency: s for s in rows}
        if any(current.get(s.dependency) != s for s in previous.selected):
            raise ValueError("selected revisions disagree with the candidate snapshot")
    return SelectionPlan(
        candidates=rows, sources=sources, derivation=derivation, update=update
    )


def complete_selection(
    plan: SelectionPlan, selected: Iterable[DependencyKey]
) -> SelectionReceipt:
    """Record a successfully executed selection, preserving the caller's order."""
    keys = tuple(selected)
    candidates = {s.dependency: s for s in plan.candidates}
    if len(set(keys)) != len(keys) or any(key not in candidates for key in keys):
        raise ValueError("selection must contain unique current candidate keys")
    return SelectionReceipt(
        materialization=materialization_receipt(
            plan.derivation,
            plan.sources,
            output_fingerprint=dependency_fingerprint(keys),
        ),
        selected=tuple(candidates[key] for key in keys),
    )
