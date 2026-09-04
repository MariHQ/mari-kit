[]{#retrieval-construction}[Reference]{.current-label}

# Hypothetical and hierarchical retrieval

## Behavior

| Mechanism | Corpus observation | What to infer |
|---|---|---|
| HyDE vector composition | QASPER evidence Recall@10 rose from `0.392` to `0.666` with a gold-answer proxy | The vector operation works. This is an oracle upper bound for generator quality |
| RAPTOR tree retrieval | QASPER evidence recall `0.426`. Complete recall `0.291` | Extractive summaries lose evidence. Summary quality must be evaluated |
| MemWalker traversal | QASPER evidence recall `0.312`. Mean nodes visited `15.7` | The measured walk budget traded fewer reads for missed leaves |
| RECOMP selection | Evidence recall `0.330` at `16.6%` of source tokens | Use the compression level when its evidence loss fits the task |

:::{collapse} Example structural differences

| Input structure | Transformation | Observable output |
|---|---|---|
| Several hypothetical-answer vectors | Weighted mean, then L2 normalization | One query vector. Generated text serves as query input |
| Eight leaf sections | Repeated reducing partitions | Tree whose root transitively covers all eight leaves |
| Scored sentences over budget | Density selection, then source-order restoration | Selected sentences in original document order |
:::



The functions construct query representations and bounded navigation
structures. Generation, encoding, clustering, summarization, and relevance
models are injected. Mari owns shape validation, deterministic IDs, budgets,
and traces.

## How it works

`hypothetical_document_embedding` weights caller-encoded hypothetical answers
and averages their vectors. L2 normalization produces the retrieval vector.
Generated text remains a query aid. `build_summary_tree` validates a
caller-proposed partition of every current root. Each accepted round creates
stable parent nodes. Tree building ends when a round keeps the same root count.
`walk_summary_tree` expands the highest-scoring children under explicit branch
and visit budgets. It returns visited paths with the exhaustion state.

::: source-block
**Papers**

[HyDE: hypothetical document embeddings](https://arxiv.org/abs/2212.10496){.paper}[RAPTOR: recursive summary trees](https://arxiv.org/abs/2401.18059){.paper}[MemWalker: bounded memory-tree navigation](https://arxiv.org/abs/2310.05029){.paper}
:::

::::::::{container} diagram flow
::: card
**Generate**[hypothetical answer]{.small}
:::

*→*

::: card
**Encode**[normalized query vector]{.small}
:::

*→*

::: card
**Retrieve**[candidate sections]{.small}
:::

*→*

::: card
**Organize**[recursive clusters]{.small}
:::

*→*

::: card
**Walk**[branch + visit budget]{.small}
:::
::::::::

## Paper-derived retrieval construction

```{code-block} python
:caption: hyde_raptor_memwalker.py · current

from mari_components.retrieval import (
    build_summary_tree, hypothetical_document_embedding, walk_summary_tree,
)

hyde_vector = hypothetical_document_embedding([
    document_encoder(text) for text in generate_hypotheses(query)
])

tree = build_summary_tree(section_text_by_id,
    cluster=lambda nodes, level: cluster_embeddings(nodes, level),
    summarize=lambda children, level: summarize(children, level))
walk = walk_summary_tree(tree, lambda node: similarity(query, node.text),
    branch_factor=2, max_visits=24)
sections = document_store.get_many(walk.leaf_ids)
```
