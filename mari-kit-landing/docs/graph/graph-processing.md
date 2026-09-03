[]{#graph-processing}[Current and proposed]{.proposed-label}

# Graph recall and corpus aggregation

Passage retrieval and corpus summarization are different operations. Personalized PageRank is a current bounded multi-hop recall function. Leiden communities and map-reduce reports are proposed, separately versioned aggregation stages.

## How it works

Link query mentions to authorized seed nodes, induce an allowed subgraph, and propagate Personalized PageRank mass until tolerance or iteration limits; project node mass back to evidence-bearing sections. Separately, Leiden partitions the graph into well-connected communities, recursive grouping forms levels, and evidence-linked community reports support global map-reduce queries. Local queries fan out from entities; drift queries start globally and open bounded local branches.

::: source-block
**Papers**

[HippoRAG: Personalized PageRank recall](https://arxiv.org/abs/2405.14831){.paper}[Leiden community detection](https://doi.org/10.1038/s41598-019-41695-z){.paper}[GraphRAG: community reports and global query](https://arxiv.org/abs/2404.16130){.paper}
:::

```{code-block} python
:caption: proposed / graph_algorithms.py

recall = PersonalizedPageRank(
    seeds=link_query(query, entities, facts), damping=0.50, hops=3,
    edge_filter=AuthorizedAt(scope=user.scope, at=query.time),
    project_to="source_sections")

communities = HierarchicalLeiden(resolution=1.0, max_size=40).fit(graph)
reports = summarize_communities(communities, evidence_policy=ExactEvidence())

answer = query_corpus(query, mode="global", reports=reports,
    reduction=RatedMapReduce(max_partial_answers=24))
```
