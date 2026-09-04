"""Provenance checks that keep derived knowledge from becoming fresh evidence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from .artifacts import ArtifactRef


class KnowledgeOrigin(StrEnum):
    SOURCE = "source"
    DERIVED = "derived"


@dataclass(frozen=True, slots=True, kw_only=True)
class DerivationInput:
    ref: ArtifactRef
    claimed_independent: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeDerivation:
    output: ArtifactRef
    origin: KnowledgeOrigin
    inputs: tuple[DerivationInput, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        if self.origin is KnowledgeOrigin.SOURCE and self.inputs:
            raise ValueError("source knowledge cannot declare derivation inputs")


class DerivationIssueKind(StrEnum):
    DUPLICATE_OUTPUT = "duplicate_output"
    MISSING_INPUT = "missing_input"
    DERIVED_AS_INDEPENDENT = "derived_as_independent"
    DERIVATION_CYCLE = "derivation_cycle"


@dataclass(frozen=True, slots=True, kw_only=True)
class DerivationIssue:
    kind: DerivationIssueKind
    output: ArtifactRef
    input_ref: ArtifactRef | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DerivationReport:
    issues: tuple[DerivationIssue, ...]
    source_roots: tuple[ArtifactRef, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def inspect_knowledge_derivations(
    records: Iterable[KnowledgeDerivation],
) -> DerivationReport:
    """Check provenance identity, missing inputs, false independence, and cycles."""

    values = tuple(records)
    counts: dict[tuple[str, str, str, str, str, str], int] = {}
    for item in values:
        counts[item.output.key] = counts.get(item.output.key, 0) + 1
    by_key = {item.output.key: item for item in values}
    issues: list[DerivationIssue] = []
    for item in values:
        if counts[item.output.key] > 1:
            issues.append(
                DerivationIssue(
                    kind=DerivationIssueKind.DUPLICATE_OUTPUT, output=item.output
                )
            )
        for dependency in item.inputs:
            parent = by_key.get(dependency.ref.key)
            if parent is None:
                issues.append(
                    DerivationIssue(
                        kind=DerivationIssueKind.MISSING_INPUT,
                        output=item.output,
                        input_ref=dependency.ref,
                    )
                )
            elif (
                dependency.claimed_independent
                and parent.origin is KnowledgeOrigin.DERIVED
            ):
                issues.append(
                    DerivationIssue(
                        kind=DerivationIssueKind.DERIVED_AS_INDEPENDENT,
                        output=item.output,
                        input_ref=dependency.ref,
                    )
                )

    visiting: set[tuple[str, str, str, str, str, str]] = set()
    visited: set[tuple[str, str, str, str, str, str]] = set()

    def visit(key: tuple[str, str, str, str, str, str]) -> None:
        if key in visiting:
            record = by_key[key]
            issues.append(
                DerivationIssue(
                    kind=DerivationIssueKind.DERIVATION_CYCLE, output=record.output
                )
            )
            return
        if key in visited:
            return
        visiting.add(key)
        for dependency in by_key[key].inputs:
            if dependency.ref.key in by_key:
                visit(dependency.ref.key)
        visiting.remove(key)
        visited.add(key)

    for key in sorted(by_key):
        visit(key)
    unique = {
        (
            item.kind,
            item.output.key,
            item.input_ref.key if item.input_ref else None,
        ): item
        for item in issues
    }
    return DerivationReport(
        issues=tuple(unique[key] for key in sorted(unique, key=repr)),
        source_roots=tuple(
            sorted(
                (
                    item.output
                    for item in values
                    if item.origin is KnowledgeOrigin.SOURCE
                ),
                key=lambda ref: ref.key,
            )
        ),
    )
