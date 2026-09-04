[]{#tags}[Supported]{.current-label}

# Tags and links

## Behavior

| Link source | Strength | Use |
|---|---|---|
| Explicit document reference | Highest | Preserve authored relationships |
| Managed tag overlay | Policy-controlled | Add vocabulary and preserve source metadata |
| Similarity-derived link | Scored and bounded | Discovery. Review before treating as identity |

On LongMemEval, the measured A-MEM threshold produced link precision `0.436` and recall `0.944`: useful for discovery, too noisy for automatic equivalence.


:::{collapse} Example tag overlay example

| Source tags | Managed change | Effective tags |
|---|---|---|
| `policy`, `draft` | Add `reviewed`. Remove `draft` | `policy`, `reviewed` |
| `policy` | Add unknown tag | Rejected before mutation |
:::


::::: split
::: card
### Managed tags

`TagDefinition`, `TagAssignments`, `assign_tags`, `normalize_tag`, and
`search_weight` store curation in an overlay. A provider resync preserves that
overlay.
:::

::: card
### Derived links

`extract_explicit_links` finds explicit references. `derive_links` adds bounded similarity links and produces typed `LinkCandidate` values.
:::
:::::

## How it works

Tag keys are normalized before add/remove set operations. Definitions validate that assignments refer to known tags. Search weight combines assigned tag weights through deterministic policy and leaves source relevance intact. Explicit-link extraction recognizes source references first. Similarity linking scores caller-supplied candidate IDs, removes self-links, applies a threshold and limit, and sorts ties stably. Returned links are proposals. The application commits and interprets them.

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

## Function definitions and options

| Function | Required inputs | Caller-controlled options |
|---|---|---|
| `assign_tags` | Prior assignments, document ID, definitions | Explicit add/remove keys |
| `normalize_tag` | One raw key | Deterministic key normalization |
| `search_weight` | Document, assignments, definitions | Weights live in caller-created definitions |
| `extract_explicit_links` | Source document and known IDs | Recognized authored references |
| `derive_links` | Source ID, candidate IDs, score callback | Threshold and result limit. Self-links are removed |

::: source-block
**Research basis**

[Similarity measures for text processing](https://doi.org/10.1145/956863.956972){.paper}[A-MEM: dynamic linked-note organization](https://arxiv.org/abs/2502.12110){.paper}

[Mari's managed-tag overlay and bounded link proposal rules are deterministic curation contracts.]{.small}
:::


Record managed tags as an explicit input when they affect a derived ranking
or artifact. The [shared dependency planner](../start/dependency-updates.md)
can invalidate those outputs independently of source-text embeddings.
