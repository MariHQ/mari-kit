[]{#artifacts}[Proposed]{.proposed-label}

# Unified artifact model

```{include} ../_includes/eval/platform.md
```

A generic envelope would give facts, answers, decisions, summaries, procedures, and graph statements common identity, scope, provenance, review, temporal, and supersession semantics.

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
:caption: proposed / artifacts.py

artifact = KnowledgeArtifact[PolicyFact](
    id="fact:refund-window:enterprise", revision="sha256:8f31…",
    value=PolicyFact(days=30),
    scope=KnowledgeScope(tenant="acme", space="support"),
    evidence=answer.evidence, valid_from="2026-01-01", valid_to=None,
    recorded_at=clock.now(), review_state=ReviewState.APPROVED,
    generated_by=Activity("refund-policy/v4", model="extractor@2026-08"),
    derived_from=("github:policy/refunds.md@8f31c2a",),
    supersedes=("fact:refund-window:enterprise@v2",))
```
