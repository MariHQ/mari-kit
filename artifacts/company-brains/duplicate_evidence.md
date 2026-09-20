> Integration note: this is the original agent report. Findings and intermediate failures below are historical; see [the integrated report](README.md) for final fixes and verification.

# Duplicate Evidence Lookup — Build Report

Order-independent citation acceptance for document-consuming knowledge parsers.

Owned artifacts (only these were created or changed):

- `src/mari_kit/knowledge/_documents.py`
- `src/mari_kit/knowledge/facts.py`
- `src/mari_kit/knowledge/answers.py`
- `src/mari_kit/knowledge/decisions.py`
- `src/mari_kit/knowledge/glossary.py`
- `src/mari_kit/knowledge/summaries.py`
- `tests/test_company_brain_duplicate_evidence.py`
- `artifacts/company-brains/duplicate_evidence.md`

## Hazard

Every document-consuming model-output parser built its citation allowance map
with a plain comprehension:

```python
allowed = {document.document_id: document for document in documents}
```

`KnowledgeDocument.document_id` is derived only from `source_id` and
`external_id`, so it is not unique in two ordinary situations:

- a provider page observed at a newer revision, and
- the same provider identity stored in two host scopes or tenants.

With conflicting inputs the dict silently keeps whichever document is iterated
last. Citation validity then depends on argument order, and the losing document
can never be cited even when its quote is present. This is the hazard pinned by
`tests/test_company_brain_isolation.py::test_parse_answer_silently_collapses_identical_document_ids`
and described as a core robustness gap in `artifacts/company-brains/isolation.md`.

The ambiguity is an input error, not an authorization decision. Hosts remain
responsible for scoping/namespaceing documents; the library must not invent
tenant authorization.

## Fix

New shared helper `mari_kit.knowledge._documents.document_lookup(documents)`
returns the `{document_id: document}` mapping and validates as it builds:

- first occurrence of a `document_id` is stored;
- a later document with the same `document_id` and an equal value is accepted
  (exact duplicate, including the same object repeated);
- a later document with the same `document_id` but a different value raises
  `ValueError("conflicting documents share document_id ...")` naming both
  revisions, before any model output is parsed.

The helper is internal (underscore module, not exported from
`mari_kit.knowledge`) and is used at all eight parser allowance callsites:

| Module | Functions |
| --- | --- |
| `facts.py` | `parse_facts`, `parse_claim_assessments` |
| `answers.py` | `parse_answer`, `parse_answer_candidates` |
| `decisions.py` | `parse_decisions` |
| `glossary.py` | `parse_glossary` |
| `summaries.py` | `parse_digest`, `parse_impact` |

Single-document model-drift repair is untouched. In `facts._evidence`, when the
allowance holds exactly one document, a model citation with an unknown
`document_id` (or a bare quote) is still repaired onto that document, because
the allowance is built before evidence binding and the single-document branch is
unchanged. The order-dependent rewrite is what changes, not repair.

## Behavior contract

- Conflicting `document_id`s: `ValueError` in either input order, raised before
  `require_list`/`require_object` touches the model output.
- Identical repeated documents: accepted and collapsed; duplicate collapse can
  no longer change the accepted evidence.
- Generators: consumed once by the helper; conflicts and exact repeats behave the
  same as with tuples/lists.
- Host scoping: `visible_refs`/`allowed_refs`/`allowed_document_ids` and any
  tenant wall are still host-owned. Mari adds no authorization logic.

## Tests

`tests/test_company_brain_duplicate_evidence.py` (28 tests) uses two local
documents that share `source_id`/`external_id` and differ only in body/revision:

- `document_lookup` collapses identical repeats (same object and `dataclasses.replace`
  copy) and rejects conflicts in both orders.
- Parametrized over all eight parser callsites: conflicting documents raise in
  either order.
- Parametrized over all eight parser callsites: the conflict raises before a
  malformed model output (`object()`) is parsed.
- Exact repeats supplied by a generator are accepted.
- `parse_answer` returns equal results for identical repeats regardless of order.
- Single-document drift repair still binds an unknown citation, while adding a
  conflicting duplicate is rejected instead of repaired.

## Commands and results

```text
$ .venv/bin/ruff format --check src/mari_kit/knowledge/_documents.py \
    src/mari_kit/knowledge/{facts,answers,decisions,glossary,summaries}.py \
    tests/test_company_brain_duplicate_evidence.py
7 files already formatted

$ .venv/bin/ruff check src/mari_kit/knowledge/_documents.py \
    src/mari_kit/knowledge/{facts,answers,decisions,glossary,summaries}.py \
    tests/test_company_brain_duplicate_evidence.py
All checks passed!

$ .venv/bin/python -m pytest tests/test_company_brain_duplicate_evidence.py -q
28 passed in 0.07s

$ .venv/bin/python -m pytest tests/test_knowledge.py -q
20 passed in 0.07s

$ .venv/bin/python -m pytest tests/ -q
3 failed, 723 passed in 2.84s
```

Focused suites are green. The full-suite failures are outside this owned change:

- `tests/test_company_brain_isolation.py::test_parse_answer_silently_collapses_identical_document_ids`
  and `::test_run_output_is_json_serializable_and_reports_isolated` assert the
  old order-dependent behavior. They are owned together with
  `examples/company_brains/isolation.py`, which was not edited here; the example
  pipes a merged two-tenant set through `parse_answer`, so it now raises
  `ValueError` as intended. Those fixtures must be updated to assert rejection
  rather than collapse, as `isolation.md` already anticipates.
- `tests/test_company_brain_conversation.py::test_resolve_locates_short_ellipsis_fragments_regression`
  fails in `resolve_evidence` quote resolution and is unrelated to document
  lookup; the working tree also carries concurrent edits to
  `src/mari_kit/knowledge/evidence.py` and `freshness.py` by another agent.

## Remaining limitations

- The helper distinguishes documents by dataclass value equality. Two records
  with the same `document_id`, revision, and body but different provider
  metadata are treated as conflicting, which is the conservative choice.
- Conflict detection happens per parser call. It does not deduplicate documents
  upstream, so hosts that merge raw provider sets should still namespace IDs per
  scope before parsing.
- `section_revisions`/`pending_fact_sections` and scoped evidence paths
  (`validate_located_evidence`, `assess_revision_refs`) are intentionally out of
  scope; they key by section or scoped ref and were not modified.
