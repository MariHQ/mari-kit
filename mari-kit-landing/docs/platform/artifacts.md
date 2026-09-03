[]{#artifacts}[Current]{.current-label}

# Unified artifact model

## At a glance

| Field group | Purpose |
|---|---|
| Identity and revision | Address an immutable artifact version |
| Scope and review state | Control visibility and activation |
| Derivation and evidence | Trace an output back to source revisions |
| Supersession and time | Preserve updates without rewriting history |


:::{collapse} Worked artifact lineage

| Field | Value |
|---|---|
| Artifact ID | `fact:refund-window:enterprise` |
| Revision | `sha256:8f31` |
| Derived from | `github:policy/refunds.md@8f31c2a` |
| Supersedes | `fact:refund-window:enterprise@v2` |
| Review state | `approved` |
:::



`KnowledgeArtifact[T]` gives facts, answers, decisions, summaries, procedures, and graph statements common identity, scope, provenance, review, temporal, and supersession semantics.

## How it works

The payload type `T` holds domain content; the envelope holds governance. Artifact identity stays stable while each revision is immutable. Evidence and `derived_from` capture inputs, `generated_by` captures the producing activity/configuration, validity bounds describe when the claim applies, and `supersedes` closes a lineage edge without erasing history. Stores reject a revision if its evidence, scope, or predecessor is invalid.

**Research basis**[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper} models entities, activities, agents, derivation, revision, and responsibility. [Nanopublications](https://arxiv.org/abs/1809.06532){.paper} attach provenance and metadata to atomic assertions. These results require first-class lineage; the single generic Python envelope is a Mari design choice to validate across artifact types.

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
