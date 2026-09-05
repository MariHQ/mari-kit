"""Optional solver-backed graph choices over caller-owned IDs and edges.

Adapters: pcst_fast (Goemans-Williamson approximation), NetworkX Louvain and
structural algorithms, graspologic-native hierarchical Leiden. See the catalog.
No solver imports occur until an operation is called.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np


def _dependency(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as error:
        raise ImportError(
            f"{name} is required; install mari-components[algorithm-solvers]"
        ) from error


def _inputs(
    nodes: Sequence[str],
    edges: Iterable[tuple[str, str, float]],
    allowed_nodes: Iterable[str] | None,
):
    if len(set(nodes)) != len(nodes) or any(not n for n in nodes):
        raise ValueError("unique nonempty node IDs required")
    known = set(nodes)
    allowed = known if allowed_nodes is None else known & set(allowed_nodes)
    rows = []
    for a, b, weight in edges:
        if a not in known or b not in known:
            raise ValueError("edge references an unknown node")
        if not math.isfinite(weight) or weight < 0:
            raise ValueError("finite nonnegative edge weights required")
        if a in allowed and b in allowed:
            rows.append((a, b, weight))
    return tuple(n for n in nodes if n in allowed), tuple(rows)


def _nx_graph(
    nodes: Sequence[str],
    edges: Iterable[tuple[str, str, float]],
    *,
    directed: bool = False,
    allowed_nodes: Iterable[str] | None = None,
):
    nx = _dependency("networkx")
    ids, rows = _inputs(nodes, edges, allowed_nodes)
    graph = nx.DiGraph() if directed else nx.Graph()
    graph.add_nodes_from(ids)
    for a, b, weight in rows:
        if graph.has_edge(a, b):
            raise ValueError("parallel edges require explicit caller aggregation")
        graph.add_edge(a, b, weight=weight)
    return nx, graph


@dataclass(frozen=True, slots=True)
class PrizeForest:
    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str, float], ...]
    total_prize: float
    total_cost: float
    root: str | None
    pruning: str


def prize_collecting_forest(
    prizes: Mapping[str, float],
    edges: Iterable[tuple[str, str, float]],
    *,
    root: str | None = None,
    clusters: int = 1,
    pruning: Literal["none", "simple", "gw", "strong"] = "strong",
    allowed_nodes: Iterable[str] | None = None,
) -> PrizeForest:
    """Select a rooted tree or unrooted forest with pcst_fast.

    Edges carry *costs*. Output references original endpoints and costs. Rooted
    calls require one cluster. This is an approximation, not an optimal solver.
    """
    if any(not math.isfinite(p) or p < 0 for p in prizes.values()):
        raise ValueError("nonnegative finite prizes required")
    ids, rows = _inputs(tuple(prizes), edges, allowed_nodes)
    if root is not None and root not in ids:
        raise ValueError("root must be an allowed node")
    if (
        clusters < 1
        or (root is not None and clusters != 1)
        or pruning not in {"none", "simple", "gw", "strong"}
    ):
        raise ValueError("invalid root/cluster/pruning selection")
    if not ids:
        return PrizeForest((), (), 0.0, 0.0, root, pruning)
    if clusters > len(ids) or any(a == b for a, b, _ in rows):
        raise ValueError("invalid cluster count or self-loop")
    index = {node: i for i, node in enumerate(ids)}
    solver = _dependency("pcst_fast")
    vertices, edge_ids = solver.pcst_fast(
        np.asarray([(index[a], index[b]) for a, b, _ in rows], dtype=np.int64).reshape(
            -1, 2
        ),
        np.asarray([prizes[node] for node in ids], dtype=float),
        np.asarray([cost for _, _, cost in rows], dtype=float),
        -1 if root is None else index[root],
        clusters,
        pruning,
        0,
    )
    selected = tuple(ids[int(i)] for i in vertices)
    selected_edges = tuple(rows[int(i)] for i in edge_ids)
    return PrizeForest(
        selected,
        selected_edges,
        sum(prizes[n] for n in selected),
        sum(c for _, _, c in selected_edges),
        root,
        pruning,
    )


def louvain_partition(
    nodes: Sequence[str],
    edges: Iterable[tuple[str, str, float]],
    *,
    resolution: float = 1.0,
    seed: int = 0,
    allowed_nodes: Iterable[str] | None = None,
) -> tuple[tuple[str, ...], ...]:
    """Undirected weighted NetworkX Louvain; isolated nodes remain singletons."""
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("positive resolution required")
    nx, graph = _nx_graph(nodes, edges, allowed_nodes=allowed_nodes)
    if graph.size(weight="weight") == 0:
        return tuple((n,) for n in sorted(graph))
    groups = nx.community.louvain_communities(
        graph, weight="weight", resolution=resolution, seed=seed
    )
    return tuple(sorted(tuple(sorted(group)) for group in groups))


@dataclass(frozen=True, slots=True)
class HierarchicalCommunity:
    node: str
    community: int
    level: int
    parent: int | None
    final: bool


def hierarchical_leiden_partition(
    nodes: Sequence[str],
    edges: Iterable[tuple[str, str, float]],
    *,
    max_cluster_size: int = 100,
    resolution: float = 1.0,
    seed: int = 0,
    allowed_nodes: Iterable[str] | None = None,
) -> tuple[HierarchicalCommunity, ...]:
    """Delegate full hierarchical Leiden to graspologic-native.

    The size is a solver splitting target, not a guarantee that every final
    community is below the threshold. Self-loops/parallel edges are rejected.
    """
    if max_cluster_size < 1 or not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("positive cluster size and resolution required")
    ids, rows = _inputs(nodes, edges, allowed_nodes)
    keys = [tuple(sorted((a, b))) for a, b, _ in rows]
    if len(set(keys)) != len(keys) or any(a == b for a, b, _ in rows):
        raise ValueError("simple undirected edges required")
    nonzero = [(a, b, w) for a, b, w in rows if w > 0]
    raw = (
        _dependency("graspologic_native").hierarchical_leiden(
            nonzero, max_cluster_size=max_cluster_size, resolution=resolution, seed=seed
        )
        if nonzero
        else []
    )
    result = [
        HierarchicalCommunity(
            row.node,
            int(row.cluster),
            int(row.level),
            None if row.parent_cluster is None else int(row.parent_cluster),
            bool(row.is_final_cluster),
        )
        for row in raw
    ]
    covered = {row.node for row in result}
    next_id = max((row.community for row in result), default=-1) + 1
    for node in ids:
        if node not in covered:
            result.append(HierarchicalCommunity(node, next_id, 0, None, True))
            next_id += 1
    return tuple(sorted(result, key=lambda row: (row.level, row.community, row.node)))


@dataclass(frozen=True, slots=True)
class Condensation:
    components: tuple[tuple[str, ...], ...]
    edges: tuple[tuple[int, int], ...]


def condense_graph(
    nodes: Sequence[str],
    edges: Iterable[tuple[str, str, float]],
    *,
    allowed_nodes: Iterable[str] | None = None,
) -> Condensation:
    """Strongly connected components and their acyclic component graph."""
    nx, graph = _nx_graph(nodes, edges, directed=True, allowed_nodes=allowed_nodes)
    groups = tuple(
        sorted(
            tuple(sorted(group)) for group in nx.strongly_connected_components(graph)
        )
    )
    owner = {node: i for i, group in enumerate(groups) for node in group}
    links = {(owner[a], owner[b]) for a, b in graph.edges if owner[a] != owner[b]}
    return Condensation(groups, tuple(sorted(links)))


def transitive_reduction_edges(
    nodes: Sequence[str], edges: Iterable[tuple[str, str, float]]
) -> tuple[tuple[str, str, float], ...]:
    """Reduce a DAG while preserving reachability and retained edge weights."""
    nx, graph = _nx_graph(nodes, edges, directed=True)
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("transitive reduction requires a DAG; condense cycles first")
    reduced = nx.transitive_reduction(graph)
    return tuple((a, b, float(graph[a][b]["weight"])) for a, b in sorted(reduced.edges))


def cohesive_subgraph(
    nodes: Sequence[str],
    edges: Iterable[tuple[str, str, float]],
    *,
    k: int,
    method: Literal["core", "truss"] = "core",
) -> tuple[str, ...]:
    """Unweighted topological k-core or k-truss selection on a simple graph."""
    if k < 0 or method not in {"core", "truss"} or (method == "truss" and k < 2):
        raise ValueError("invalid cohesion method or k")
    nx, graph = _nx_graph(nodes, edges)
    if nx.number_of_selfloops(graph):
        raise ValueError("cohesion requires a loop-free graph")
    selected = nx.k_core(graph, k) if method == "core" else nx.k_truss(graph, k)
    return tuple(sorted(selected.nodes))
