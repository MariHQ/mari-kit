[]{#evidence}[Core]{.current-label}

# Evidence contracts

## Contract

| Claim state | Required evidence behavior |
|---|---|
| Supported | At least one resolvable source span entails the claim |
| Contradicted | At least one resolvable span conflicts with the claim |
| Uncertain | Evidence is missing, malformed, inaccessible, or inconclusive |

Mari validates references against exact document and section revisions. The injected model or evaluator supplies entailment and citation-quality scores.

`ObjectRef` and `RevisionRef` carry scope, namespace, object identity, revision,
and an optional stable unit. `LocatedEvidence` combines that reference with a
typed locator. `ArtifactRef`, `ArtifactEvidence`, and document-specific
`Evidence` remain available during the compatibility migration.

| Locator | Material addressed |
|---|---|
| `TextSpan` | Character range in normalized text |
| `JsonPointer` | Value inside JSON-compatible material |
| `RecordField` | Named field on a stable record |
| `TableCell` | Row and column in a tabular value |
| `PageRegion` | Bounding box on a numbered page |
| `MediaTimeRange` | Time interval in audio or video |


:::{collapse} Example evidence resolution examples

| Proposal | Source state | Result |
|---|---|---|
| Exact quote and matching offsets | Matching revision | Accepted with provenance |
| Exact quote | Unknown revision | Rejected |
| Paraphrase supplied as literal quote | Matching revision | Rejected |
| No resolvable evidence | Any | Explicit `insufficient_evidence` answer |
:::

:::::{container} diagram evidence
::: source
[refunds.md · rev 8f31c2a]{.small}

Enterprise refunds close after [30 days]{.mark}.
:::

::: bridge
literal containment + unique section
:::

::: record
**Evidence**

`document_id = …refunds.md`

`revision = 8f31c2a`

`quote = "30 days"`

`start = 31 · end = 38`

`section_id = enterprise`

`section_revision = sha256:…`
:::
:::::

```{code-block} python
:caption: evidence.py

from mari_components.knowledge import parse_facts

raw = {"facts": [{
    "claim": "Enterprise refunds close after 30 days.",
    "evidence": [{"document_id": doc.document_id,
                  "section_id": "enterprise",
                  "quote": "30 days"}],
}]}
fact = parse_facts([doc], raw)[0]
e = fact.evidence[0]
assert doc.body[e.start:e.end] == e.quote

# Rejected: unknown document, absent quote, or a repeated quote
# whose section cannot be selected unambiguously.
```

```{code-block} python
:caption: Validate citations against exactly what the model saw

from mari_components.knowledge import (
    ArtifactEvidence, ArtifactRef, validate_artifact_evidence,
)

visible = ArtifactRef(
    artifact_id="policy", revision="v8", unit_id="enterprise",
)
evidence = ArtifactEvidence(
    ref=visible, quote="30 days", start=31, end=38,
)

report = validate_artifact_evidence(
    [evidence],
    visible_refs=[visible],
    resolve_text=lambda ref: rendered_units.get(ref.key),
)

assert report.accepted
```

```{code-block} python
:caption: Resolve evidence from structured material

from mari_components import JsonPointer, ObjectRef, RevisionRef
from mari_components.knowledge import LocatedEvidence, validate_located_evidence

source = RevisionRef(
    object=ObjectRef(namespace="crm", object_id="account:42", scope=scope),
    revision="crm-v7",
)
evidence = LocatedEvidence(
    ref=source,
    locator=JsonPointer(pointer="/plan/monthly_price"),
    quote="599",
)
report = validate_located_evidence(
    [evidence],
    visible_refs=[source],
    resolve_material=lambda ref: material_by_revision.get(ref.key),
)
assert report.accepted
```

The report separates `not_visible`, `unresolved`, `invalid_span`,
`unsupported_locator`, and `quote_mismatch`. Page and media locators accept an
application locator callback. Mari stays independent of the selected PDF or
media runtime. Applications decide whether the evidence is sufficient,
independent, authorized, or persuasive.

## Dependency conversion

`evidence_dependencies` projects each record to `(document_id, document_revision, section_id, section_revision)`, deduplicated by `(document_id, section_id)` and returned in stable order. Two records naming different revisions of the same key raise `ValueError`. Silently choosing one would make reuse nondeterministic.

**Contract boundary.** The record proves that quoted characters occurred in one supplied source revision and records their location. Entailment, source authority, completeness, and truth require claim assessment, corroboration, authorization, and review.

::: source-block
**Research and standards**

[ALCE: citation correctness and completeness](https://arxiv.org/abs/2305.14627){.paper}[QASPER: evidence-bearing document QA](https://arxiv.org/abs/2105.03011){.paper}[FActScore: atomic factual claims](https://arxiv.org/abs/2305.14251){.paper}[FEVER: evidence-backed verdicts](https://arxiv.org/abs/1803.05355){.paper}[W3C PROV: quotation, derivation, and revision](https://www.w3.org/TR/prov-dm/){.paper}

[These works motivate inspectable evidence and revision provenance. Literal substring validation, unique-section resolution, and failure behavior are Mari engineering contracts.]{.small}
:::


An evidence record is a byte-for-byte quotation bound to the exact document and section revision supplied to a parser. It carries provenance. A model confidence score comes from a separate field.

## How it works

1.  **Restrict the corpus.** Build an allowed map from the `KnowledgeDocument` values passed by the caller. Reject model citations outside that map.
2.  **Resolve the document.** Require `document_id`. If exactly one allowed document contains the quote, Mari recovers a missing ID. Zero or multiple holders is rejected.
3.  **Match exact text.** Require a non-empty quote and test literal containment in the canonical document body. The contract requires literal text.
4.  **Resolve one section.** Split the document into current sections and find sections containing the quote. A repeated quote spanning multiple sections is rejected unless `section_id` selects exactly one.
5.  **Derive coordinates.** Mari computes `start = section.start + section.body.index(quote)` and `end = start + len(quote)`. Model-supplied offsets and revisions are ignored.
6.  **Bind revisions.** The accepted record receives the current `document.revision`, stable `section_id`, and content-derived `section.revision`. These become the invalidation key.
