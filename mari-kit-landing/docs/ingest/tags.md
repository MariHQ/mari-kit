[]{#tags}[Current]{.current-label}

# Tags and links

## Evaluation

Tag evaluation checks assignment validation and deterministic search weighting, while note-evolution cases independently exercise similarity and link thresholds. No external clustering or A-MEM task score is claimed.

```console
$ pytest -q tests/test_knowledge.py tests/test_research_extensions.py -k 'tag or note_links'
2 passed
```

::: card
## Derived links

`extract_explicit_links` finds explicit references. `derive_links` adds bounded similarity links and produces typed `LinkCandidate` values.
:::
:::::

## How it works

Tag keys are normalized before add/remove set operations; definitions validate that assignments refer to known tags. Search weight combines assigned tag weights through deterministic policy rather than rewriting source relevance. Explicit-link extraction recognizes source references first. Similarity linking scores only caller-supplied candidate IDs, removes self-links, applies a threshold and limit, and sorts ties stably. Returned links are proposals; committing and interpreting them remains application policy.

```{code-block} python
:caption: curation.py

from mari_components.knowledge import (
    TagAssignments, TagDefinition, assign_tags, derive_links, search_weight,
)

definitions = {"canonical": TagDefinition(key="canonical", label="Canonical",
    kind="canonical", search_weight=2.0, behaviors=("Wins conflicts",))}
assignments = assign_tags(TagAssignments(), doc.document_id, definitions,
    add=("canonical",))
weight = search_weight(doc.document_id, assignments, definitions)
links = derive_links(doc.document_id, candidate_ids,
    score=lambda source, target: similarity_scores[source, target])
```

::: source-block
**Research basis**

[Similarity measures for text processing](https://doi.org/10.1145/956863.956972){.paper}[A-MEM: dynamic linked-note organization](https://arxiv.org/abs/2502.12110){.paper}

[Mari's managed-tag overlay and bounded link proposal rules are deterministic curation contracts.]{.small}
:::


::::: split
::: card
## Managed tags

`TagDefinition`, `TagAssignments`, `assign_tags`, `normalize_tag`, and `search_weight` keep curation separate from provider-owned documents, so resync does not erase it.
:::
