[]{#projections}[Proposed]{.proposed-label}

# Event sourcing and disposable projections

```{include} ../_includes/eval/graph.md
```

Canonical artifacts and append-only events remain authoritative. Search indexes, backlink tables, graph views, digests, and human-readable logs are projections with explicit build identities and safe swap semantics.

## How it works

Append a validated event with an expected generation, fold ordered events through a deterministic projector into a staging version, and record schema plus embedding/configuration fingerprints. Validate counts, checksums, scope isolation, and sample queries before atomically switching the current pointer. A failed replay never replaces the last valid projection, and retaining the prior pointer makes rollback constant-time.

::: source-block
**Papers and standards**

[Data pipeline reproducibility](https://arxiv.org/abs/2006.12117){.paper}[Invariant confluence](https://arxiv.org/abs/1402.2237){.paper}[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper}
:::

::::::{container} diagram projection-flow
<div>

**Canonical artifacts**[documents · events · reviews]{.small}

</div>

*deterministic fold*

<div>

**Staging projections**[vector · lexical · graph · Markdown]{.small}

</div>

*validate + swap*

<div>

**Current read version**[rollback pointer retained]{.small}

</div>
::::::

```{code-block} python
:caption: proposed / projections.py

events.append(KnowledgeEvent(kind="artifact.superseded", payload=mutation,
    actor=reviewer, expected_generation=41))

build = rebuild_projection(events, projector=SearchProjector(
    embedding_identity=embedder.fingerprint(), schema_version="3"))
validate(build, checks=[DocumentCount(), Checksums(), ScopeIsolation(), SampleQueries()])
projections.atomic_swap(build, retain_previous=True)

# A failed build never replaces the last valid read version.
```
