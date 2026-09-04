[]{#subgraph-selection}[Reference]{.current-label}

# Bounded evidence subgraphs

## Behavior

| Method | Preserves connectivity | Optimization claim | Use |
|---|---:|---|---|
| `bounded_seed_expansion` | Optional | Bounded traversal | Collect readable k-hop evidence under a node budget |
| `prize_guided_subgraph` | Yes | Deterministic greedy heuristic | Trade relevance prize against edge cost |
| `pcst_fast` adapter | Yes | Upstream approximation guarantee | Larger prize-collecting problems |

Mari's built-in prize-collecting method is a deterministic greedy heuristic.

## How it works

Seed expansion ranks frontier nodes using a caller score and stops at a hard node/depth budget. Prize-guided selection starts with the best seed, then repeatedly adds the cheapest path whose newly collected prize exceeds its edge cost. The result records the accepted nodes, edges, total prize, total cost, and rejected frontier candidates.

```{code-block} python
:caption: Select connected evidence through callbacks

from mari_components.graph import prize_guided_subgraph

selection = prize_guided_subgraph(
    seeds=("claim:refund-window",),
    neighbors=store.neighbors,
    prize=lambda node: retrieval_scores.get(node, 0.0),
    edge_cost=lambda left, right: store.edge_cost(left, right),
    max_nodes=12,
)
```

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
