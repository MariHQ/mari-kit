[]{#freshness}[Core]{.current-label}

# Freshness and impact

## Contract

| Dependency state | Artifact status | Action |
|---|---|---|
| Same document and section revision | Fresh | Reuse |
| Unrelated section changed | Fresh for a section-scoped dependency | Reuse |
| Referenced section changed or disappeared | Stale | Recompute or review |
| Current revision unavailable | Unknown | Require an explicit refresh decision |

Freshness compares recorded dependencies with the current revision map. Impact performs the reverse lookup from a changed dependency to derived artifacts.

## Coordinate updates across modules

Use `assess_freshness` or `assess_revision_refs` to inspect an existing
artifact's revision dependencies. Use
[`plan_dependency_updates`](../start/dependency-updates.md) to coordinate
recomputation across atoms, embeddings, artifacts, and projections.

| Planner action | Meaning | Host action |
|---|---|---|
| `REUSE` | Completed receipt matches the recipe and current inputs | Read the stored output |
| `REBUILD` | Inputs are available and work is due | Compute and atomically publish output plus receipt |
| `WAIT` | An upstream output is being rebuilt | Replan after successful upstream publication |
| `BLOCKED` | A required input is unavailable | Restore the input or revise the graph explicitly |

The planner compares actual completed output fingerprints. An upstream
rebuild that produces identical material can preserve downstream results.
Include ordered membership for aggregate outputs and recipe configuration for
model or prompt changes. Access-policy stamps invalidate affected projections.
Read-time authorization remains a separate application check.

`assess_revision_refs` applies the same exact comparison to any structurally
addressed object. Documents, CRM records, media, graph assertions, procedures,
and derived artifacts share `ObjectRef` and `RevisionRef`.


:::{collapse} Example revision outcomes

| Change | Bound dependency | Reuse decision |
|---|---|---|
| Edit to cited section | Old section revision | Rebuild |
| Edit to unrelated section | Cited section unchanged | Reuse |
| Source removed | Missing dependency | Rebuild or withdraw |
| Principal loses access | Dependency visibility revoked | Reject reuse |
:::

::::::{container} diagram dependency
<div>

**Policy answer**[depends on § window]{.small}

</div>

::: bridge
revision lookup
:::

::: changed
**§ window**[30 → 45 days]{.small}
:::

::: bridge
reverse dependency lookup
:::

<div>

**Refresh queue**[affected artifacts]{.small}

</div>
::::::

:::{container} status-order
<div class="missing"><b>1 · missing</b><small>source or section absent</small></div>
<div class="unversioned"><b>2 · unversioned</b><small>cannot compare safely</small></div>
<div class="stale"><b>3 · stale</b><small>revision differs</small></div>
<div class="current"><b>4 · current</b><small>all revisions equal</small></div>
:::

```{code-block} python
:caption: freshness.py

from mari_components.knowledge import (
    FreshnessStatus, assess_dependencies, assess_freshness,
    impacted_artifacts,
)

report = assess_freshness(answer.evidence, current_revisions,
    current_section_revisions=current_sections)
if not report.reusable:
    refresh(report.changes, report.missing_dependency_ids)

stale = impacted_artifacts(dependencies_by_artifact, current_revisions,
    current_section_revisions=current_sections)
```

```{code-block} python
:caption: Assess a structured record dependency

from mari_components.knowledge import assess_revision_refs

report = assess_revision_refs(
    expected=[account_revision_used_by_fact],
    current={account_object_ref: current_account_revision},
)
```

## Document edit versus affected section

```{code-block} python
:caption: granularity.py

# The document changed v1 → v2. The cited section remains s1.
current_revisions = {doc_id: "v2"}
current_sections = {(doc_id, "refund-window"): "s1"}

fine = assess_dependencies(deps, current_revisions,
    current_section_revisions=current_sections)
assert fine.status == FreshnessStatus.CURRENT

coarse = assess_dependencies(deps, current_revisions)
assert coarse.status == FreshnessStatus.STALE  # safe fallback
```

**Operational consequence.** Section hashes preserve an answer when an unrelated section changed. A missing section map triggers conservative refreshes. Only `current` sets `report.reusable` to true.

::: source-block
**Research and standards**

[Build Systems à la Carte: dependency-driven recomputation](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}[RAG: updateable non-parametric knowledge and provenance](https://arxiv.org/abs/2005.11401){.paper}[W3C PROV: revision and derivation](https://www.w3.org/TR/prov-dm/){.paper}

[Mari applies build-system invalidation to knowledge artifacts. Status precedence, section fallback, and reuse policy are explicit Mari contracts. Semantic change detection requires another layer.]{.small}
:::


Freshness compares input revisions exactly. It answers "did an input revision change?" Semantic answer quality requires a separate assessment.

## How it works

1.  **Record dependencies.** Every derived artifact stores the document or section revision used to build it.
2.  **Select comparison granularity.** If a dependency names a section and the caller supplies a section-revision map, compare section hashes. Otherwise compare the containing document revision as a conservative fallback.
3.  **Classify every key.** Missing document/section → `missing`. Empty expected/current revision → `unversioned`. Unequal revisions → `stale`. Otherwise → `current`.
4.  **Reduce deterministically.** Status precedence is `missing > unversioned > stale > current`. Changes and IDs are sorted, so the same inputs produce the same report.
5.  **Propagate impact.** `impacted_artifacts` evaluates each artifact independently and returns non-current artifacts. Mari reports the set. The application chooses whether to regenerate, review, or retire them.
