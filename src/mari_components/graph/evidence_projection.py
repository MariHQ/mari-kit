"""Many-to-many projections from graph values to evidence artifacts."""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import TypeVar

from mari_components.knowledge.artifacts import ArtifactRef

NodeT = TypeVar("NodeT", bound=Hashable)


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphEvidenceAssociation:
    node: Hashable
    artifact: ArtifactRef
    node_score: float
    path: tuple[Hashable, ...]
    role: str = "evidence"


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphEvidenceProjection:
    associations: tuple[GraphEvidenceAssociation, ...]
    missing_nodes: tuple[Hashable, ...]

    @property
    def artifact_refs(self) -> tuple[ArtifactRef, ...]:
        values = {
            association.artifact.key: association.artifact
            for association in self.associations
        }
        return tuple(values[key] for key in sorted(values))


def project_graph_evidence(
    nodes: Iterable[NodeT],
    *,
    artifacts: Callable[[NodeT], Iterable[ArtifactRef]],
    score: Callable[[NodeT], float] = lambda _node: 0.0,
    path: Callable[[NodeT], Iterable[NodeT]] = lambda node: (node,),
    role: Callable[[NodeT, ArtifactRef], str] = lambda _node, _ref: "evidence",
) -> GraphEvidenceProjection:
    """Retain every node/artifact association instead of collapsing the join."""

    associations: list[GraphEvidenceAssociation] = []
    missing: list[NodeT] = []
    for node in nodes:
        node_score = float(score(node))
        if not math.isfinite(node_score):
            raise ValueError("graph evidence scores must be finite")
        refs = tuple(artifacts(node))
        if not refs:
            missing.append(node)
            continue
        node_path = tuple(path(node))
        for ref in refs:
            association_role = role(node, ref)
            if not association_role.strip():
                raise ValueError("graph evidence role is required")
            associations.append(
                GraphEvidenceAssociation(
                    node=node,
                    artifact=ref,
                    node_score=node_score,
                    path=node_path,
                    role=association_role,
                )
            )
    return GraphEvidenceProjection(
        associations=tuple(
            sorted(
                associations,
                key=lambda value: (
                    repr(value.node),
                    value.artifact.key,
                    value.role,
                ),
            )
        ),
        missing_nodes=tuple(sorted(missing, key=repr)),
    )
