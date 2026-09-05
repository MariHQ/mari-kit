[]{#graph-processing}[Reference]{.current-label}

# Graph recall and corpus aggregation

## Behavior

| Mechanism | Corpus observation | Decision guidance |
|---|---|---|
| Personalized PageRank | QASC passage Recall@5 `0.850`. Both gold facts found `0.709` | Graph expansion exposed many two-hop facts. Complete chains appeared in `0.709` of cases |
| Local-modularity community heuristic | DocRED relation-community coverage `0.430`. Mean modularity `0.518` | Co-mention graphs form coherent groups and split many gold relations |
| Community reports | Deterministic partition and bounded map/reduce | Report quality depends on the injected summarizer |

:::{collapse} Example graph propagation example

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

Link query mentions to authorized seed nodes, induce an allowed subgraph, and
propagate Personalized PageRank mass until tolerance or iteration limits.
Project node mass back to evidence-bearing sections.

`leiden_communities` is a historical compatibility name for deterministic local
modularity improvement followed by connected-component splitting. It averages
opposing edge weights and drops self-links. Its output is a flat heuristic
partition. Full Leiden additionally requires an aggregation phase. For native hierarchical Leiden, Louvain,
and bounded DRIFT search, see the independently selectable
[algorithm choices](../start/algorithm-choices.md). Evidence binding and model
callbacks remain caller-supplied.

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

`build_community_reports` invokes the summarizer once per community and retains
node IDs with each report. `map_reduce_reports` processes the first `limit`
reports in supplied order. Rank reports before this call when relevance should
determine the subset. Token budgets and model-call execution belong to those
callbacks.

## Incremental report maintenance

Treat a community report as a derived artifact with explicit membership,
source revisions, summarizer version, and configuration inputs. Community IDs
such as `community:0` are local partition positions. Assign durable scoped
identity before caching reports across partitions. The
[shared dependency planner](../start/dependency-updates.md) can reuse completed
reports whose inputs match and hold dependent answers until changed reports
finish rebuilding.
