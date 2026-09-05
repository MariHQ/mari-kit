# Evidence-preserving context and conversations

Mari provides five composable operations for document retrieval and conversation
context. They accept values and return inspectable results. The host chooses
storage, authorization, model prompts, tokenization, and message rendering.

Run the credential-free integration:

```bash
python -m examples.evidence_context_demo
```

## Expand retrieved evidence using document structure

`mari_components.retrieval.expand_structured_context` accepts
`StructuredContextItem` values and scored `ContextHit` references. Construct items
from existing semantic atoms with `context_items_from_atoms`, or from a
`ParsedDocument` with `context_items_from_document`. Source identity uses
`ObjectRef` and `RevisionRef`, including the caller's scope.

```python
from mari_components.retrieval import (
    ContextExpansionPolicy, ContextHit, context_items_from_atoms,
    expand_structured_context,
)

items = context_items_from_atoms(atoms, source=source_ref)
result = expand_structured_context(
    items,
    [ContextHit(ref=items[0].evidence.ref, score=0.9)],
    policy=ContextExpansionPolicy(max_chars=4000),
    allowed_refs=authorized_current_unit_refs,
)
```

An enclosing section is retained whole when it fits. Larger sections expand
outward around the matched item and are clipped around the evidence anchor.
Small prose sections may grow into adjacent sections; figure and table matches
stay within their own sections. Overlapping windows merge only if every matched
anchor can survive. Adjacent windows do not merge merely because they touch.

A hit may specify a `TextSpan` **relative to its item's text**. That span must
survive whole; an oversized span appears in `over_budget_refs`. Without an
explicit span, expansion retains a central anchor of up to 128 characters,
limited by the budget. Each fragment reports its exact retained `item_span`.
Existing source `TextSpan` locators are narrowed accordingly. A structural JSON
pointer continues to identify its whole item; the fragment span identifies the
rendered excerpt within it. Page metadata is narrowed to surviving items, not
inferred at character granularity inside a multi-page item.

`max_chars` limits **each window**, including separators. It is not a global
token limit. The host can tokenize and pack returned windows using Mari's existing
context selection tools. Existing `assemble_atom_context` remains available for
whole-atom selection under one token budget.

Excluded labels, tight labels, small-section ratio, anchor size, and separator
are explicit policy values. No labels are excluded by default. Even an excluded
label is retained when it is directly matched. Unauthorized items partition the
sequence; no window includes their text. The host must provide sufficient source
structure to identify the intended section boundaries. Unknown hit references
and duplicate item identities are errors rather than silent fallbacks.

## Inspect declarations across evidence owners

`mari_components.knowledge.inspect_citation_declarations` consumes immutable
`CitationEvent` values for one activity. Event ordinals establish order across
all evidence owners within that activity; they do not depend on transcript
length. `OwnedEvidenceRef` includes both an owner and a full source revision.

- `OUTCOME` records evidence shown, including a search with no results.
- `DECLARATION` records the evidence an answer attributes itself to; an empty
  declaration explicitly attributes it to no evidence.
- A declaration must occur strictly after the newest outcome from **every** owner.
  A later search makes earlier declarations stale.
- Repeated current declarations union references. An empty second declaration
  cannot erase citations from the same evidence epoch.
- References must be published by a preceding outcome or supplied through
  `available_evidence` for evidence already shown before this activity.

The report distinguishes `missing`, `stale`, `declared`, `empty`, and `invalid`.
It does not establish semantic entailment, decide whether citations are required,
retry an agent, or modify an answer. Continue using answer/evidence validators for
source resolution; applications choose any enforcement behavior.

## Plan conversation evidence compaction

`plan_evidence_compaction` builds on `KnowledgeObservation` records. Supply
canonical `CompactionEvidence` values, an explicit activity order ending with the
current activity, and currently allowed evidence and asset revision references.
Observation artifact IDs must be namespaced by the host, with one unambiguous
canonical record per `(artifact_id, revision)` pair and one observation identity
per canonical evidence unit. Aliases are rejected to prevent double retention.

The plan groups previously cited evidence by its newest citing activity, newest
first, and keeps each unit whole. Uncited retrieval payloads are not retained.
Evidence observed in the current activity is protected from historical
compaction. Missing canonical records for historical citations are errors.

A caller-supplied `token_count` represents the intended per-unit rendering cost;
include associated asset costs if they should consume the same budget. A finite
budget greedily admits complete units in recency order; `None` retains all
eligible cited units. Reserve shared headers and separators in the host's budget.
The trace reports not-cited, current-activity, unavailable, and budget exclusions.
Revision and authorization decisions must be reevaluated before each reuse.

`compact_observation_ids` identifies historical retrieved/shown observations
whose **request payloads** the host may replace. `protected_observation_ids`
identifies current activity observations. These are observation IDs, not runtime
message offsets. The host must map them to its own messages and preserve unrelated
content and user attachments. The plan never edits the durable transcript.

## Map Docling exports to existing Mari document types

```python
from mari_components.documents.docling import adapt_docling_json

result = adapt_docling_json(
    docling_document.model_dump(mode="json"),
    source=source_ref,
    revision="source-revision",
    media_type="application/pdf",
)
adapted = result.values[0]
```

The adapter accepts DoclingDocument schema version 1 JSON and returns a
`ParseResult[DoclingAdaptation]` containing a `ParsedDocument`, a
`StructuredDocument`, located evidence, asset bindings, and parse issues. It
preserves body reading order, nested blocks, source pointers, labels, heading
levels, page numbers, and table cells with row/column spans. Furniture can be
included or omitted explicitly. Bottom-left page boxes are converted into
Mari's top-left boxes using the source page height.

Generated descriptions remain separate `RegionRepresentation` and asset fields;
they never replace source captions. Tables use a simple row/tab text rendering
alongside structured cells. Joined captions and rendered tables are not emitted
as verbatim quotes in the adapter's evidence list. Missing or invalid geometry
produces an issue without inventing a region. Pictures without geometry still
have asset references. Invalid trees, missing pointers, and unsupported schema
major versions are rejected.

This adapter has **no Docling dependency**. It does not convert files, perform
OCR, load image URIs, decode images, or invoke models. Retain source JSON or
another asset resolver outside Mari if later asset loading is needed.

## Select multimodal evidence assets

`select_evidence_assets` takes `AssetBinding` values, retained located evidence,
currently allowed asset revisions, and optional already-attached references.
It returns deduplicated `RetainedAsset` values with all surviving supporting
references and an explicit retrieved-evidence origin. Caption text and generated
descriptions remain separate.

Asset identity includes scope, source namespace, object, revision, and unit.
The same `#/pictures/0` in two documents or tenants therefore remains distinct.
Assets belonging only to discarded fragments are omitted, and conflicting
metadata for one retained asset revision is rejected. Bytes, MIME validation,
provider payloads, and labels shown to a model remain application responsibilities.

## Origin and validation

These operations adapt behavior from the local haiku.rag 0.82.1 source:
`context.py`, `capabilities/ledger.py`, `capabilities/compaction.py`,
`store/models/document_item.py`, and `tools/search.py`. Its MIT notice is retained
in `THIRD_PARTY_NOTICES.md` and included in distribution license files.

Regression tests cover clipped evidence, overlap splitting, revision/permission
boundaries, missing and stale declarations, explicit empty declarations,
compaction budgets, scoped image identities, reading order, coordinate conversion,
and generated-description separation. Deterministic randomized context cases
check hit retention and source-span fidelity. These are correctness tests;
retrieval relevance and answer-quality improvements have not been benchmarked.
