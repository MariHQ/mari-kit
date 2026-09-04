[]{#artifacts}[Core]{.current-label}

# Unified artifact model

## Artifact fields

| Field group | Purpose |
|---|---|
| Identity and revision | Address an immutable artifact version |
| Scope and review state | Control visibility and activation |
| Derivation and evidence | Trace an output back to source revisions |
| Supersession and time | Preserve every historical revision |


:::{collapse} Artifact lineage example

| Field | Value |
|---|---|
| Artifact ID | `fact:refund-window:enterprise` |
| Revision | `sha256:8f31` |
| Derived from | `github:policy/refunds.md@8f31c2a` |
| Supersedes | `fact:refund-window:enterprise@v2` |
| Review state | `approved` |
:::



`KnowledgeArtifact[T]` gives each knowledge value a shared envelope. Facts and
answers use it. Decisions, summaries, procedures, and graph statements use the
same fields for identity and scope. The envelope also carries provenance,
review state, time bounds, and supersession links.

## How it works

The payload type `T` holds domain content. Its envelope records the controls
around that content. Artifact identity stays stable across immutable revisions.
Evidence links record inputs. `generated_by` identifies the producing activity
and configuration. Validity bounds mark when a claim applies. A `supersedes`
link closes the lineage edge and keeps the earlier revision. Stores reject a
revision when evidence, scope, or predecessor checks fail.

**Research basis**[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper}
models entities and their revisions. It also records activities, agents,
derivation, and responsibility. [Nanopublications](https://arxiv.org/abs/1809.06532){.paper}
attach provenance and metadata to atomic assertions. These results motivate
first-class lineage. Mari uses one generic Python envelope so the same checks
work across artifact types.

:::::{container} diagram artifact
<div>

**KnowledgeArtifact\[T\]**

</div>

<div>

identity + revisionKnowledgeScopeevidencevalid timereview stategeneratorsupersedes

</div>
:::::

```{code-block} python
:caption: Immutable, provenance-bearing artifact revision

from datetime import datetime, timezone

from mari_components.knowledge import (
    Activity,
    KnowledgeArtifact,
    KnowledgeScope,
    ReviewState,
)

artifact = KnowledgeArtifact[dict[str, int]](
    artifact_id="fact:refund-window:enterprise",
    revision="sha256:8f31",
    value={"days": 30},
    scope=KnowledgeScope(tenant="acme", space="support"),
    recorded_at=datetime.now(timezone.utc),
    review_state=ReviewState.APPROVED,
    generated_by=Activity(
        identifier="refund-policy/v4",
        implementation="extractor@2026-08",
    ),
    derived_from=("github:policy/refunds.md@8f31c2a",),
    supersedes=("fact:refund-window:enterprise@v2",),
)
```
