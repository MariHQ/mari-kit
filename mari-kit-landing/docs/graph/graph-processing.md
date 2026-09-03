[]{#graph-processing}[Current]{.current-label}

# Graph recall and corpus aggregation

## Evaluation

Five deterministic cases evaluate ACL-bounded Personalized PageRank, multi-hop activation, passage projection, connected deterministic community partitions, and injected map/reduce calls. The HippoRAG, Leiden, and GraphRAG mechanisms are therefore checked at the library boundary. QASC, KILT, and DocRED task scores have not been run.

```console
$ pytest -q tests/test_retrieval_algorithms.py -k GraphRetrieval
$ pytest -q tests/test_graph_communities.py
5 passed
```


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
