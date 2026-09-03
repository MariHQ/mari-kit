[]{#retrieval-construction}[Current]{.current-label}

# Hypothetical and hierarchical retrieval

These functions construct alternative query representations and bounded navigation structures. Generation, encoding, clustering, summarization, and relevance models are injected; Mari owns shape validation, deterministic IDs, budgets, and traces.

## How it works

`hypothetical_document_embedding` weights and averages caller-encoded hypothetical answers, then L2-normalizes the vector used for retrieval; generated text is never stored as fact. `build_summary_tree` repeatedly validates a caller-proposed partition of every current root, creates stable parent nodes, and stops when the root count no longer decreases. `walk_summary_tree` expands the highest-scoring children under explicit branch and visit budgets and returns visited paths plus exhaustion state.

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
