[]{#pipelines}[Proposed]{.proposed-label}

# Typed knowledge pipelines

```{include} ../_includes/eval/platform.md
```

Composable stages would transform typed inputs and emit reviewable `ArtifactMutation` values: create, revise, supersede, retract, or leave unchanged.

## How it works

Each stage declares input/output types, a versioned configuration fingerprint, and whether it is pure or calls an injected service. The runner topologically orders stages, passes immutable batches, records input revisions and stage results, and stops dependent stages after failure. Outputs are mutation proposals; a final policy validates evidence, scope, and expected artifact revision before the application commits them.

**Research basis**[Pipeline provenance research](https://arxiv.org/abs/2006.12117){.paper} ties reproducibility to captured inputs, transformations, and configuration. [Data Cascades](https://doi.org/10.1145/3411764.3445518){.paper} documents how upstream data failures compound downstream. This motivates stage identities, dependency traces, and visible failures; the generic stage and mutation types are Mari\'s composition boundary.

:::{container} diagram stages
extract*→*resolve*→*link*→*review*→*index
:::

```{code-block} python
:caption: proposed / pipeline.py

pipeline = Pipeline[KnowledgeDocument, KnowledgeArtifact](
    extract(FactExtractor(model=model)), resolve(EntityResolver(catalog=entities)),
    link(EvidenceLinker()), review(ReviewPolicy(min_corroboration=2)),
    index(vector=vector_index, graph=graph_index))

result = pipeline.run(changed_documents)
artifact_store.apply(result.mutations)
trace_store.write(result.trace)
```
