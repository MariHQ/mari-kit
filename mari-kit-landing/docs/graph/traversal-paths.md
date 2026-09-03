[]{#traversal-paths}[Current]{.current-label}

# Traversal, reachability, and paths

## Behavior

| Need | Function | Caller supplies |
|---|---|---|
| Explore outward | `breadth_first` | Start IDs and `neighbors(id)` |
| Find the cheapest route | `shortest_path` | Start, target, neighbors, and edge cost |
| Bound context expansion | `k_hop_nodes` | Seeds, direction-specific neighbors, maximum depth |
| Partition topology | `connected_components` | Node IDs and undirected neighbors |

## How it works

Mari accepts IDs and callbacks. Algorithms operate on hashable IDs and return
immutable results with visited-node counts and path cost. Stable ordering uses
a caller-supplied key when IDs lack a natural textual identity.

```{code-block} python
:caption: Traverse application-owned storage

from mari_components.graph import shortest_path

path = shortest_path(
    "customer:42",
    "policy:refunds",
    neighbors=lambda node: store.outgoing_ids(node),
    edge_cost=lambda left, right: 1.0 - store.confidence(left, right),
    allowed=lambda node: can_read(node),
    max_depth=5,
)

if path.found:
    context.add(path.nodes)
```

Use `build_adjacency` to project caller edge iterables in the incoming,
outgoing, or both direction. `predecessor_dag` retains every predecessor on an
unweighted shortest path. Alternative explanations remain beside one
BFS parent.

```{code-block} python
:caption: Retain two equally short impact paths

from mari_components.graph import build_adjacency, predecessor_dag

outgoing = build_adjacency(
    call_edges, endpoints=lambda edge: (edge.caller, edge.callee),
)
paths = predecessor_dag(
    [changed_symbol], neighbors=outgoing.__getitem__, max_depth=5,
)

for entry in paths.entries:
    print(entry.node, entry.predecessors, entry.shortest_path_count)
```

When edge payloads carry citation intent, relation version, time, or provenance,
use `traverse_edges`. The caller supplies edge enumeration, adjacency, node
authorization, and an edge rejection function. Results preserve accepted edges
and rejected edges with reasons.

```{code-block} python
:caption: Traverse citations and retain retraction decisions

from mari_components.graph import traverse_edges

trace = traverse_edges(
    [review_id],
    edges=citation_store.outgoing,
    adjacent=lambda source, citation: citation.target,
    reject_edge=lambda citation: "retracted" if citation.retracted else None,
    max_depth=3,
)
```

Outgoing edges hidden by `max_depth` are returned as rejected edges with
`reason="depth_limit"`, and `truncated` becomes true. This distinguishes a leaf
from an unexplored traversal boundary.

Breadth-first traversal gives minimum hop count in an unweighted graph. Weighted paths use Dijkstra's algorithm and reject negative or non-finite costs. Authorization is checked before a node enters the frontier.

## Measures

| Property | Check |
|---|---|
| Correctness | Compare paths and components with NetworkX fixtures |
| Determinism | Shuffle neighbor order and require identical output |
| Isolation | Paths and visited traces exclude forbidden nodes |
| Bounds | Depth and visited-node budgets stop expansion exactly |

`evaluate_path(predicted, expected)` reports exact match plus node- and edge-level precision and recall. Edge scores distinguish a route that visits the right nodes in the wrong order from a correct path.

::: source-block
**Papers and implementations**

[Dijkstra's shortest path](https://doi.org/10.1007/BF01386390){.paper}[NetworkX algorithms](https://github.com/networkx/networkx){.paper}[Breadth-first search](https://doi.org/10.1109/T-C.1972.223138){.paper}

[NetworkX is BSD-3-Clause and serves as a differential reference. It remains outside the runtime dependency set.]{.small}
:::
