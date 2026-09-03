[]{#freshness}[Current]{.current-label}

# Freshness and impact

```{include} ../_includes/eval/govern.md
```

Freshness is an exact dependency comparison. It answers "did an input revision change?"---not "is the answer still semantically correct?"

## How it works

1.  **Record dependencies.** Every derived artifact stores the document or section revision used to build it.
2.  **Select comparison granularity.** If a dependency names a section and the caller supplies a section-revision map, compare section hashes. Otherwise compare the containing document revision as a conservative fallback.
3.  **Classify every key.** Missing document/section → `missing`; empty expected/current revision → `unversioned`; unequal revisions → `stale`; otherwise → `current`.
4.  **Reduce deterministically.** Overall precedence is `missing > unversioned > stale > current`. Changes and IDs are sorted, so the same inputs produce the same report.
5.  **Propagate impact.** `impacted_artifacts` evaluates each artifact independently and returns only non-current artifacts. Mari reports the set; the application chooses whether to regenerate, review, or retire them.

::::::{container} diagram dependency
<div>

**Policy answer**[depends on § window]{.small}

</div>

![](data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMTIwIDQwIj48cGF0aCBkPSJNMCAyMCBDNDUgMjAgNzUgMjAgMTIwIDIwIiAvPjwvc3ZnPg==)

::: changed
**§ window**[30 → 45 days]{.small}
:::

![](data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMTIwIDQwIj48cGF0aCBkPSJNMCAyMCBDNDUgMjAgNzUgMjAgMTIwIDIwIiAvPjwvc3ZnPg==)

<div>

**Refresh queue**[only affected artifacts]{.small}

</div>
::::::

:::{container} status-order
[**1 · missing**[source or section absent]{.small}]{.missing}[**2 · unversioned**[cannot compare safely]{.small}]{.unversioned}[**3 · stale**[revision differs]{.small}]{.stale}[**4 · current**[all revisions equal]{.small}]{.current}
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

## Document edit versus affected section

```{code-block} python
:caption: granularity.py

# The document changed v1 → v2, but the cited section is still s1.
current_revisions = {doc_id: "v2"}
current_sections = {(doc_id, "refund-window"): "s1"}

fine = assess_dependencies(deps, current_revisions,
    current_section_revisions=current_sections)
assert fine.status == FreshnessStatus.CURRENT

coarse = assess_dependencies(deps, current_revisions)
assert coarse.status == FreshnessStatus.STALE  # safe fallback
```

**Operational consequence**Section hashes avoid regenerating an answer when an unrelated section changed. Omitting the section map intentionally increases false-positive refreshes rather than risking stale reuse. Only `current` sets `report.reusable` to true.

::: source-block
**Research and standards**

[Build Systems à la Carte: dependency-driven recomputation](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}[RAG: updateable non-parametric knowledge and provenance](https://arxiv.org/abs/2005.11401){.paper}[W3C PROV: revision and derivation](https://www.w3.org/TR/prov-dm/){.paper}

[Mari applies build-system invalidation to knowledge artifacts. Status precedence, section fallback, and reuse policy are explicit Mari contracts, not semantic change detection.]{.small}
:::
