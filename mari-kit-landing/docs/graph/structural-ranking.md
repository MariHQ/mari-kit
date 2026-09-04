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

Centrality functions receive node IDs and neighbor callbacks. Personalized
PageRank accepts a weighted adjacency mapping through the retrieval API.
They return scores, with labels left to callers. Betweenness uses the unweighted
Brandes algorithm. HITS and PageRank expose iteration and convergence settings.

Restrict both the node collection and neighbor callbacks to the same authorized
graph. Degree and closeness can follow neighbors outside the supplied node
collection. Closeness follows the callback direction, so incoming and outgoing
adjacency answer different questions. For large graphs, repeated all-source
traversals make closeness and betweenness more expensive than degree ranking.

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

degree_by_node = dict(degree)
bridges_by_node = dict(bridges)
features = {
    node: {
        "degree": degree_by_node.get(node, 0.0),
        "betweenness": bridges_by_node.get(node, 0.0),
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
