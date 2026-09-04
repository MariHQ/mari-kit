[]{#subgraph-selection}[Reference]{.current-label}

# Bounded evidence subgraphs

## Behavior

| Method | Preserves connectivity | Optimization claim | Use |
|---|---:|---|---|
| `bounded_seed_expansion` | Each addition connects to a seed component | Bounded traversal | Collect readable k-hop evidence under a node budget |
| `prize_guided_subgraph` | Each addition connects to a seed component | Deterministic greedy heuristic | Trade relevance prize against edge cost |
| External `pcst_fast` | Solver-dependent | Consult upstream solver contract | Caller-integrated prize-collecting optimization |

Mari's built-in prize-collecting method is a deterministic greedy heuristic.

## How it works

Seed expansion ranks each frontier using a caller score and stops at a hard node/depth budget. Prize-guided selection retains allowed seeds up to the node budget, then repeatedly adds the adjacent node with the largest positive prize minus edge cost. The result records selected nodes, accepted edges, total prize, total cost, and rejected frontier candidates.

Multiple seeds can produce disconnected components. A single seed gives a connected selection. The greedy rule can miss a valuable distant node behind a low-prize bridge. Use an application-integrated optimizer when whole-path tradeoffs matter. `pcst_fast` is an external option requiring a caller adapter.

```{code-block} python
:caption: Select connected evidence through callbacks

from mari_components.graph import prize_guided_subgraph

selection = prize_guided_subgraph(
    seeds=("claim:refund-window",),
    neighbors=store.neighbors,
    prize=lambda node: retrieval_scores.get(node, 0.0),
    edge_cost=lambda left, right: store.edge_cost(left, right),
    max_nodes=12,
    allowed=can_read,
)
```

`max_nodes` bounds selected output size. High-degree neighbor enumeration can still be expensive. Bound the callback's candidate set separately, and account for rendered token size before adding the selected evidence to context.

## Measures

| Measure | Meaning |
|---|---|
| Evidence recall | Required evidence nodes present in the selected subgraph |
| Connectedness | Every selected node is reachable from a seed |
| Prize minus cost | Transparent heuristic objective |
| Context size | Nodes, edges, and rendered tokens |
| Exact gap on small graphs | Compare with exhaustive or exact PCST solutions |

::: source-block
**Papers and implementations**

[G-Retriever](https://arxiv.org/abs/2402.07630){.paper}[Goemans--Williamson PCST](https://doi.org/10.1137/S0097539794279106){.paper}[pcst_fast](https://github.com/fraenkel-lab/pcst_fast){.paper}

[`pcst_fast` is MIT licensed. Mari's dependency-free heuristic has a different, documented contract.]{.small}
:::
