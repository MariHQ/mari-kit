[]{#retrieval-construction}[Current]{.current-label}

# Hypothetical and hierarchical retrieval

## Evaluation

| Mechanism | Cases | Result | Corpus result |
|---|---:|---:|---|
| HyDE centroid construction | 2 | 2 / 2 pass | Not measured |
| RAPTOR tree and MemWalker traversal | 3 | 3 / 3 pass | Not measured |
| RECOMP selection and ordering | 2 | 2 / 2 pass | Not measured |

:::{collapse} Worked structural differences

| Input structure | Transformation | Observable output |
|---|---|---|
| Several hypothetical-answer vectors | Weighted mean, then L2 normalization | One query vector; generated text is not stored |
| Eight leaf sections | Repeated reducing partitions | Tree whose root transitively covers all eight leaves |
| Scored sentences over budget | Density selection, then source-order restoration | Only selected sentences, in original document order |
:::

### Reproduce

```console
$ pytest -q tests/test_research_extensions.py -k 'Hyde or RaptorAndMemWalker or Recomp'
```


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
