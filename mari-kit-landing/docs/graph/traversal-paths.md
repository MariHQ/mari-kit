[]{#traversal-paths}[Current]{.current-label}

# Traversal, reachability, and paths

## At a glance

| Need | Function | Caller supplies |
|---|---|---|
| Explore outward | `breadth_first` | Start IDs and `neighbors(id)` |
| Find the cheapest route | `shortest_path` | Start, target, neighbors, and edge cost |
| Bound context expansion | `k_hop_nodes` | Seeds, direction-specific neighbors, maximum depth |
| Partition topology | `connected_components` | Node IDs and undirected neighbors |

## How it works

Mari never receives a graph instance. Algorithms operate on hashable IDs and callbacks, and return immutable results with visited-node counts and path cost. Stable ordering requires a caller-supplied key when IDs do not have a natural textual identity.

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

Breadth-first traversal gives minimum hop count in an unweighted graph. Weighted paths use Dijkstra's algorithm and reject negative or non-finite costs. Authorization is checked before a node enters the frontier.

## What to evaluate

| Property | Check |
|---|---|
| Correctness | Compare paths and components with NetworkX fixtures |
| Determinism | Shuffle neighbor order and require identical output |
| Isolation | Forbidden nodes never appear in paths or visited traces |
| Bounds | Depth and visited-node budgets stop expansion exactly |

`evaluate_path(predicted, expected)` reports exact match plus node- and edge-level precision and recall. Edge scores distinguish a route that visits the right nodes in the wrong order from a correct path.

::: source-block
**Papers and implementations**

[Dijkstra's shortest path](https://doi.org/10.1007/BF01386390){.paper}[NetworkX algorithms](https://github.com/networkx/networkx){.paper}[Breadth-first search](https://doi.org/10.1109/T-C.1972.223138){.paper}

[NetworkX is BSD-3-Clause and is used as a differential reference, not a runtime dependency.]{.small}
:::
