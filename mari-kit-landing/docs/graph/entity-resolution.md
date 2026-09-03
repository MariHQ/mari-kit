[]{#entity-resolution}[Proposed]{.proposed-label}

# Entity resolution with explicit uncertainty

```{include} ../_includes/eval/graph.md
```

The cascade spends expensive work only after cheap deterministic checks. It never converts an ambiguous candidate into a merge without a configured threshold or review decision.

## How it works

Block candidates by tenant, scope, and entity type; compare normalized exact aliases; calculate field-agreement and fuzzy scores; retrieve a small embedding neighborhood only for unresolved candidates; then apply separate link and review thresholds. Scores above link become a proposed canonical ID, scores in the review band retain all candidates and their feature trace, and lower scores remain distinct entities.

::: source-block
**Papers**

[Fellegi--Sunter: probabilistic record linkage](https://doi.org/10.1080/01621459.1969.10501049){.paper}
:::

:::{container} diagram resolution-cascade
scope + type block*→*normalized exact*→*field/fuzzy score*→*embedding candidates*→*link · reject · review
:::

```{code-block} python
:caption: proposed / resolve.py

resolver = EntityResolver([
    ScopeAndTypeBlock(), NormalizedAliasMatch(),
    ProbabilisticFieldMatch(link=0.95, review=0.72),
    EmbeddingCandidates(index=entity_index, limit=10),
])
resolution = resolver.resolve(candidate, scope=artifact.scope)
if resolution.ambiguous:
    review_queue.put(resolution.candidates, resolution.comparison_trace)
```
