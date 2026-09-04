"""Atom-hit aggregation and retrieval-time context assembly."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from mari_components.documents.atoms import SemanticAtom

from .maxsim import exact_maxsim


@dataclass(frozen=True, slots=True, kw_only=True)
class AtomVectorHit:
    atom_id: str
    source_id: str
    section_id: str
    score: float

    def __post_init__(self) -> None:
        if (
            not self.atom_id.strip()
            or not self.source_id.strip()
            or not self.section_id.strip()
            or not math.isfinite(self.score)
        ):
            raise ValueError("atom hit identity and finite score are required")


@dataclass(frozen=True, slots=True, kw_only=True)
class ParentVectorHit:
    parent_id: str
    score: float
    atom_ids: tuple[str, ...]
    atom_scores: tuple[float, ...]


def aggregate_atom_hits(
    hits: Iterable[AtomVectorHit],
    *,
    parent: str = "section",
    weights: Sequence[float] = (1.0, 0.4, 0.2),
) -> tuple[ParentVectorHit, ...]:
    """Group ANN atom hits using weighted top scores rather than a mean."""

    if (
        parent not in {"section", "source"}
        or not weights
        or any(not math.isfinite(weight) or weight < 0 for weight in weights)
    ):
        raise ValueError("parent and non-negative finite weights are required")
    grouped: dict[str, dict[str, float]] = {}
    for hit in hits:
        parent_id = (
            f"{hit.source_id}#{hit.section_id}"
            if parent == "section"
            else hit.source_id
        )
        values = grouped.setdefault(parent_id, {})
        values[hit.atom_id] = max(hit.score, values.get(hit.atom_id, -math.inf))
    output: list[ParentVectorHit] = []
    for parent_id, values in grouped.items():
        ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))
        contributing = ranked[: len(weights)]
        output.append(
            ParentVectorHit(
                parent_id=parent_id,
                score=sum(
                    score * weight
                    for (_, score), weight in zip(contributing, weights, strict=False)
                ),
                atom_ids=tuple(atom_id for atom_id, _ in contributing),
                atom_scores=tuple(score for _, score in contributing),
            )
        )
    return tuple(sorted(output, key=lambda item: (-item.score, item.parent_id)))


@dataclass(frozen=True, slots=True, kw_only=True)
class MultiVectorSection:
    section_id: str
    source_id: str
    title_vector: tuple[float, ...] | None
    section_vector: tuple[float, ...] | None
    atom_vectors: Mapping[str, tuple[float, ...]]
    contextual_atom_vectors: Mapping[str, tuple[float, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "atom_vectors", MappingProxyType(dict(self.atom_vectors))
        )
        object.__setattr__(
            self,
            "contextual_atom_vectors",
            MappingProxyType(dict(self.contextual_atom_vectors)),
        )

    def matrix(
        self, *, contextual: bool = True, include_parent_vectors: bool = True
    ) -> NDArray[np.float32]:
        values: list[Sequence[float]] = []
        if include_parent_vectors:
            if self.title_vector is not None:
                values.append(self.title_vector)
            if self.section_vector is not None:
                values.append(self.section_vector)
        mapping = self.contextual_atom_vectors if contextual else self.atom_vectors
        values.extend(mapping[key] for key in sorted(mapping))
        matrix = np.asarray(values, dtype=np.float32)
        if matrix.ndim != 2 or not len(matrix) or not np.all(np.isfinite(matrix)):
            raise ValueError("section vectors must be a non-empty finite matrix")
        return matrix


def maxsim_section_score(
    query_vectors: Sequence[Sequence[float]],
    section: MultiVectorSection,
    *,
    contextual: bool = True,
    query_weights: Sequence[float] | None = None,
) -> float:
    """Apply exact late interaction to caller-generated query and section vectors."""

    query = np.asarray(query_vectors, dtype=np.float32)
    weights = (
        None if query_weights is None else np.asarray(query_weights, dtype=np.float32)
    )
    return exact_maxsim(
        query,
        section.matrix(contextual=contextual),
        query_weights=weights,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class DynamicContextChunk:
    source_id: str
    section_id: str
    atom_ids: tuple[str, ...]
    hit_atom_ids: tuple[str, ...]
    text: str
    token_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DynamicContextResult:
    chunks: tuple[DynamicContextChunk, ...]
    selected_atom_ids: tuple[str, ...]
    skipped_hit_ids: tuple[str, ...]
    token_count: int


def assemble_atom_context(
    atoms: Iterable[SemanticAtom],
    *,
    hit_atom_ids: Iterable[str],
    token_counts: Mapping[str, int],
    token_budget: int,
    neighbors: int = 2,
    separator: str = "\n\n",
) -> DynamicContextResult:
    """Expand hit atoms to nearby atoms at query time under one token budget."""

    if token_budget < 0 or neighbors < 0:
        raise ValueError("token budget and neighbors must not be negative")
    values = tuple(
        sorted(atoms, key=lambda atom: (atom.source_id, atom.section_id, atom.ordinal))
    )
    by_id = {atom.atom_id: atom for atom in values}
    if len(by_id) != len(values) or set(by_id) - token_counts.keys():
        raise ValueError("atoms require unique IDs and token counts")
    requested = tuple(dict.fromkeys(hit_atom_ids))
    if set(requested) - by_id.keys():
        raise ValueError("hit references an unknown atom")
    sections: dict[tuple[str, str], list[SemanticAtom]] = {}
    for atom in values:
        sections.setdefault((atom.source_id, atom.section_id), []).append(atom)
    candidate_ids: list[str] = list(requested)
    hits_by_section: dict[tuple[str, str], list[str]] = {}
    for hit_id in requested:
        hit = by_id[hit_id]
        key = (hit.source_id, hit.section_id)
        hits_by_section.setdefault(key, []).append(hit_id)
    for distance in range(1, neighbors + 1):
        for hit_id in requested:
            hit = by_id[hit_id]
            key = (hit.source_id, hit.section_id)
            members = sections[key]
            position = members.index(hit)
            for neighbor_position in (position - distance, position + distance):
                if 0 <= neighbor_position < len(members):
                    atom_id = members[neighbor_position].atom_id
                    if atom_id not in candidate_ids:
                        candidate_ids.append(atom_id)
    selected: set[str] = set()
    used = 0
    for atom_id in candidate_ids:
        count = token_counts[atom_id]
        if count < 1:
            raise ValueError("atom token counts must be positive")
        if used + count <= token_budget:
            selected.add(atom_id)
            used += count
    chunks: list[DynamicContextChunk] = []
    for key, members in sorted(sections.items()):
        run: list[SemanticAtom] = []
        for atom in (*members, None):
            if atom is not None and atom.atom_id in selected:
                run.append(atom)
                continue
            if not run:
                continue
            atom_ids = tuple(value.atom_id for value in run)
            chunks.append(
                DynamicContextChunk(
                    source_id=key[0],
                    section_id=key[1],
                    atom_ids=atom_ids,
                    hit_atom_ids=tuple(
                        atom_id
                        for atom_id in hits_by_section.get(key, ())
                        if atom_id in atom_ids
                    ),
                    text=separator.join(value.text for value in run),
                    token_count=sum(token_counts[value.atom_id] for value in run),
                )
            )
            run = []
    selected_ids = tuple(atom_id for atom_id in candidate_ids if atom_id in selected)
    return DynamicContextResult(
        chunks=tuple(chunks),
        selected_atom_ids=selected_ids,
        skipped_hit_ids=tuple(hit_id for hit_id in requested if hit_id not in selected),
        token_count=used,
    )
