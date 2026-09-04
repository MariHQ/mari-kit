"""Shared dependency receipts and incremental planning for derived material.

Receipts describe completed work. Plans never stand in for receipts: downstream
work waits for an upstream output fingerprint, allowing unchanged outputs to
stop invalidation even when their inputs changed.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from graphlib import TopologicalSorter
from typing import Any

from .json import canonical_json_bytes, freeze_json_mapping
from .references import ObjectRef, RevisionRef


def dependency_fingerprint(value: Any) -> str:
    """Fingerprint exact, canonical input material without text normalization."""
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyKey:
    """One aspect of an object or unit in its existing isolation scope."""

    object: ObjectRef
    aspect: str = "content"
    unit_id: str = ""

    def __post_init__(self) -> None:
        if not self.aspect.strip():
            raise ValueError("dependency aspect is required")
        object.__setattr__(self, "aspect", self.aspect.strip())
        object.__setattr__(self, "unit_id", self.unit_id.strip())

    @property
    def key(self) -> tuple[str, ...]:
        return (*self.object.key, self.unit_id, self.aspect)

    @classmethod
    def from_revision(cls, ref: RevisionRef) -> DependencyKey:
        return cls(object=ref.object, unit_id=ref.unit_id, aspect="revision")


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyStamp:
    dependency: DependencyKey
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.fingerprint.strip():
            raise ValueError("dependency fingerprint is required")

    @classmethod
    def from_revision(cls, ref: RevisionRef) -> DependencyStamp:
        return cls(
            dependency=DependencyKey.from_revision(ref), fingerprint=ref.revision
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DerivationSpec:
    """Declared inputs and a versioned computation for one output aspect.

    Input order is significant. Include model, prompt, parser and configuration
    versions here, and collection-membership stamps for dynamically selected inputs.
    """

    output: DependencyKey
    inputs: tuple[DependencyKey, ...]
    implementation: str
    configuration: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.implementation.strip():
            raise ValueError("derivation implementation and version are required")
        inputs = tuple(self.inputs)
        if len(set(inputs)) != len(inputs):
            raise ValueError("derivation inputs must be unique")
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(
            self, "configuration", freeze_json_mapping(self.configuration)
        )

    @property
    def fingerprint(self) -> str:
        return dependency_fingerprint(
            {"implementation": self.implementation, "configuration": self.configuration}
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterializationReceipt:
    """An actual stored output and the exact inputs used to produce it."""

    output: DependencyStamp
    inputs: tuple[DependencyStamp, ...]
    implementation_fingerprint: str

    def __post_init__(self) -> None:
        inputs = tuple(self.inputs)
        if len({item.dependency for item in inputs}) != len(inputs):
            raise ValueError("receipt inputs must be unique")
        if not self.implementation_fingerprint.strip():
            raise ValueError("receipt implementation fingerprint is required")
        object.__setattr__(self, "inputs", inputs)


def materialization_receipt(
    spec: DerivationSpec,
    inputs: Iterable[DependencyStamp],
    *,
    output_fingerprint: str,
) -> MaterializationReceipt:
    """Record successful materialization; persist this with the output atomically."""
    values = tuple(inputs)
    if tuple(value.dependency for value in values) != spec.inputs:
        raise ValueError("receipt inputs must match declared inputs in order")
    return MaterializationReceipt(
        output=DependencyStamp(dependency=spec.output, fingerprint=output_fingerprint),
        inputs=values,
        implementation_fingerprint=spec.fingerprint,
    )


class UpdateAction(StrEnum):
    REUSE = "reuse"
    REBUILD = "rebuild"
    WAIT = "wait"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyUpdate:
    output: DependencyKey
    action: UpdateAction
    reasons: tuple[str, ...]
    dependencies: tuple[DependencyKey, ...] = ()
    inputs: tuple[DependencyStamp, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyUpdatePlan:
    updates: tuple[DependencyUpdate, ...]
    available: tuple[DependencyStamp, ...]
    retired: tuple[DependencyKey, ...]

    @property
    def ready(self) -> tuple[DependencyUpdate, ...]:
        return tuple(
            item for item in self.updates if item.action is UpdateAction.REBUILD
        )

    @property
    def reusable(self) -> tuple[DependencyKey, ...]:
        return tuple(
            item.output for item in self.updates if item.action is UpdateAction.REUSE
        )


def plan_dependency_updates(
    *,
    sources: Iterable[DependencyStamp],
    derivations: Iterable[DerivationSpec],
    materializations: Iterable[MaterializationReceipt] = (),
) -> DependencyUpdatePlan:
    """Plan against a complete caller-selected snapshot and dependency DAG.

    Missing sources block their dependents, including previously cached outputs.
    Dirty upstream outputs are withheld until successful materialization. Replan
    with the resulting receipts to expose the next ready frontier. Omitted source
    stamps mean unavailable, not unchanged. Retired outputs are hints, not deletes.
    """
    available: dict[DependencyKey, DependencyStamp] = {}
    for stamp in sources:
        previous = available.get(stamp.dependency)
        if previous is not None and previous != stamp:
            raise ValueError("conflicting source dependency stamps")
        available[stamp.dependency] = stamp
    specs: dict[DependencyKey, DerivationSpec] = {}
    for spec in derivations:
        if spec.output in specs or spec.output in available:
            raise ValueError("dependency outputs must have one producer")
        specs[spec.output] = spec
    receipts: dict[DependencyKey, MaterializationReceipt] = {}
    for receipt in materializations:
        if receipt.output.dependency in receipts:
            raise ValueError("materialization outputs must be unique")
        receipts[receipt.output.dependency] = receipt

    graph = {
        key: spec.inputs
        for key, spec in sorted(specs.items(), key=lambda item: item[0].key)
    }
    # TopologicalSorter rejects cycles and avoids recursion on long derivation chains.
    ordered = tuple(TopologicalSorter(graph).static_order())
    updates: list[DependencyUpdate] = []
    blocked: set[DependencyKey] = set()
    for output in ordered:
        if output not in specs:
            continue
        spec = specs[output]
        missing = tuple(
            key
            for key in spec.inputs
            if (key not in specs and key not in available) or key in blocked
        )
        waiting = tuple(
            key
            for key in spec.inputs
            if key in specs and key not in available and key not in blocked
        )
        if missing:
            blocked.add(output)
            updates.append(
                DependencyUpdate(
                    output=output,
                    action=UpdateAction.BLOCKED,
                    reasons=("unavailable_input",),
                    dependencies=missing,
                )
            )
            continue
        if waiting:
            updates.append(
                DependencyUpdate(
                    output=output,
                    action=UpdateAction.WAIT,
                    reasons=("upstream_pending",),
                    dependencies=waiting,
                )
            )
            continue
        inputs = tuple(available[key] for key in spec.inputs)
        receipt = receipts.get(output)
        reasons: list[str] = []
        changed: tuple[DependencyKey, ...] = ()
        if receipt is None:
            reasons.append("not_materialized")
        else:
            if receipt.implementation_fingerprint != spec.fingerprint:
                reasons.append("implementation_changed")
            if tuple(item.dependency for item in receipt.inputs) != spec.inputs:
                reasons.append("input_set_changed")
            prior = {item.dependency: item.fingerprint for item in receipt.inputs}
            changed = tuple(
                item.dependency
                for item in inputs
                if prior.get(item.dependency) != item.fingerprint
            )
            if changed:
                reasons.append("input_changed")
        if not reasons and receipt is not None:
            available[output] = receipt.output
        updates.append(
            DependencyUpdate(
                output=output,
                action=UpdateAction.REBUILD if reasons else UpdateAction.REUSE,
                reasons=tuple(reasons),
                dependencies=changed,
                inputs=inputs,
            )
        )
    return DependencyUpdatePlan(
        updates=tuple(updates),
        available=tuple(
            available[key] for key in sorted(available, key=lambda value: value.key)
        ),
        retired=tuple(
            sorted(receipts.keys() - specs.keys(), key=lambda value: value.key)
        ),
    )
