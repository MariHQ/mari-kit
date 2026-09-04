[]{#structural-ranking}[Reference]{.current-label}

# Structural ranking

## Behavior

| Algorithm | Signal | Appropriate comparison |
|---|---|---|
| Degree centrality | Immediate connectivity | Local prominence |
| Closeness centrality | Mean shortest-path distance | Reachability from one node |
| Betweenness centrality | Fraction of shortest paths crossing a node | Bridges and bottlenecks |
| HITS | Mutually reinforcing hubs and authorities | Directed link structure |
| Personalized PageRank | Stationary visit probability from seeds | Query-biased graph retrieval |

## How it works

All functions receive node IDs and neighbor callbacks. They return scores, with labels left to callers. Betweenness uses the unweighted Brandes algorithm. HITS and PageRank expose iteration and convergence settings so approximate results are reproducible.

```{code-block} python
:caption: Compare caller-selected structural signals

from mari_components.graph import (
    betweenness_centrality,
    degree_centrality,
    hits,
)

degree = degree_centrality(node_ids, neighbors=undirected_neighbors)
bridges = betweenness_centrality(node_ids, neighbors=outgoing_neighbors)
hub_authority = hits(node_ids, successors=outgoing_neighbors)

features = {
    node: {
        "degree": dict(degree).get(node, 0.0),
        "betweenness": dict(bridges).get(node, 0.0),
    }
    for node in node_ids
}
```

## Measures

| Property | Check |
|---|---|
| Numerical conformance | Compare small fixtures with NetworkX |
| Directionality | Run asymmetric graphs with explicit successor callbacks |
| Disconnected graphs | Verify closeness normalization and unreachable nodes |
| Convergence | Record iterations, tolerance, and residual |
| Retrieval value | Compare evidence recall across baseline and structural-score runs |

::: source-block
**Papers and implementations**

[Brandes betweenness](https://doi.org/10.1080/0022250X.2001.9990249){.paper}[HITS](https://www.cs.cornell.edu/home/kleinber/auth.pdf){.paper}[PageRank](https://ilpubs.stanford.edu:8090/422/1/1999-66.pdf){.paper}[NetworkX](https://github.com/networkx/networkx){.paper}

[NetworkX is the BSD-3-Clause differential oracle. Mari accepts graph access
through callbacks. The caller sets any global ranking policy.]{.small}
:::
