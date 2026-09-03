[]{#graph-processing}[Current]{.current-label}

# Graph recall and corpus aggregation

## At a glance

| Mechanism | Corpus observation | Decision guidance |
|---|---|---|
| Personalized PageRank | QASC passage Recall@5 `0.850`; both gold facts found `0.709` | Graph expansion helps expose two-hop evidence, but does not guarantee complete chains |
| Leiden communities | DocRED relation-community coverage `0.430`; mean modularity `0.518` | Co-mention graphs form coherent groups while splitting many gold relations |
| Community reports | Deterministic partition and bounded map/reduce | Report quality still depends on the injected summarizer |

:::{collapse} Worked graph propagation example

| Node | Relation to seed | Allowed | Retrieval outcome |
|---|---|---:|---|
| `refund-policy` | Seed | Yes | Ranked |
| `enterprise-exception` | Two hops away | Yes | Activated by propagation |
| `private-escalation` | One hop away | No | Removed before propagation |

| Community input | Output invariant |
|---|---|
| Disconnected candidate cluster | Split into connected components |
| Same graph and resolution | Same deterministic partition |
:::



Passage retrieval and corpus summarization are different operations. Personalized PageRank is a bounded multi-hop recall function. Deterministic community partitioning and model-injected map-reduce reports are separately versioned aggregation stages.

## How it works

Link query mentions to authorized seed nodes, induce an allowed subgraph, and propagate Personalized PageRank mass until tolerance or iteration limits; project node mass back to evidence-bearing sections. Separately, Leiden partitions the graph into well-connected communities, recursive grouping forms levels, and evidence-linked community reports support global map-reduce queries. Local queries fan out from entities; drift queries start globally and open bounded local branches.

::: source-block
**Papers**

[HippoRAG: Personalized PageRank recall](https://arxiv.org/abs/2405.14831){.paper}[Leiden community detection](https://doi.org/10.1038/s41598-019-41695-z){.paper}[GraphRAG: community reports and global query](https://arxiv.org/abs/2404.16130){.paper}
:::

```{code-block} python
:caption: Authorized recall and community map-reduce

from mari_components.graph import (
    build_community_reports,
    leiden_communities,
    map_reduce_reports,
)
from mari_components.retrieval import personalized_pagerank

recall = personalized_pagerank(
    graph,
    seeds=query_seeds,
    allowed_node_ids=authorized_node_ids,
    damping=0.50,
)

partition = leiden_communities(
    graph,
    resolution=1.0,
    allowed_node_ids=authorized_node_ids,
)
reports = build_community_reports(partition, summarize=summarize_nodes)
answer = map_reduce_reports(
    reports,
    map_report=lambda report: answer_from_report(query, report),
    reduce_answers=lambda partials: synthesize(query, partials),
    limit=24,
)
```
