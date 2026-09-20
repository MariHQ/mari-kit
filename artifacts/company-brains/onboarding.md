> Integration note: this is the original agent report. Findings and intermediate failures below are historical; see [the integrated report](README.md) for final fixes and verification.

# Onboarding company brain: build report

## Build outcome

Complete. The onboarding company brain is a compact, credential-free module:

| Path | Role |
| --- | --- |
| `examples/company_brains/onboarding.py` | `run() -> dict` plus deterministic fixtures; `__main__` prints JSON |
| `tests/test_company_brain_onboarding.py` | 12 behavioral tests, including failure paths |
| `artifacts/company-brains/onboarding.md` | This report |

`run()` takes no arguments, reads no environment variables, performs no network
or filesystem access, and returns a JSON-serializable dictionary. It reuses the
real Mari Kit public APIs throughout; no algorithm is re-implemented and no
wrapper swallows a library exception.

The scenario models an employee onboarding brain over three synthetic
documents: a public onboarding handbook with `Welcome`, `Equipment`, and
`Security training` sections, a public IT setup guide, and a restricted People
Operations HR policy. A reviewed exact-substring policy edit changes only the
`Equipment` section.

## Required behaviors exercised

| Requirement | Where it is shown | Result |
| --- | --- | --- |
| Facts from exact section evidence | `parse_facts` with explicit `section_id`; spans and section revisions recomputed by the library | 3 facts bound to `welcome`, `equipment`, `security-training` |
| Policy edit detection | `parse_refinement` proposes the edit; `section_revisions` finds changed section | `handbook/onboarding#equipment` |
| Unchanged-section reuse | `assess_freshness` with `current_section_revisions` | `welcome` and `security-training` stay `current` after the document revision changes |
| Conservative fallback | `assess_freshness` without a section map | whole handbook `stale` |
| Incremental re-extraction | `pending_fact_sections` vs. stored section checkpoints | only `equipment` is pending; the other two facts are reused |
| Missing / invalid evidence | `parse_facts` rejects unknown documents and invented quotes; `parse_claim_assessments` downgrades unverifiable citations to `uncertain`; `parse_answer` returns `insufficient_evidence`; `assess_freshness` reports `missing` for a retired source and a removed section | all four paths asserted |
| Restricted HR documents | `DocumentACL` recorded by the library, host mapping to `allowed_document_ids`, `search_index` authorization-before-scoring, host fact filtering | HR policy hidden from an engineer, visible to People Operations |

## Public APIs used

`KnowledgeDocument`, `DocumentACL`, `Principal`, `Evidence`, `FactCandidate`,
`parse_facts`, `parse_refinement`, `section_revisions`, `assess_freshness`,
`pending_fact_sections`, `deduplicate_fact_candidates`, `parse_answer`,
`parse_claim_assessments`, `build_index`, `search_index`.

## Commands and results

```text
.venv/bin/python -m pytest tests/test_company_brain_onboarding.py -q
  12 passed

.venv/bin/ruff format --check examples/company_brains/onboarding.py tests/test_company_brain_onboarding.py
  2 files already formatted

.venv/bin/ruff check examples/company_brains/onboarding.py tests/test_company_brain_onboarding.py
  All checks passed!

.venv/bin/python -m examples.company_brains.onboarding
  JSON object with 21 keys (see below for the load-bearing values)
```

Load-bearing `run()` values:

```text
changed_sections                = ["handbook/onboarding#equipment"]
section_status_after_edit       = {welcome: current, equipment: stale, security-training: current}
document_level_fallback_status  = "stale"
pending_sections_after_edit     = ["handbook/onboarding#equipment"]
reused_unchanged_section_facts  = 2 claims
unknown_document_citation_rejected = true
invented_quote_rejected            = true
unverifiable_assessment_verdict    = "uncertain"
insufficient_evidence_disposition  = "insufficient_evidence"
missing_evidence_status            = "missing"
restricted_hr_hidden_from_employee = true
employee_served_hr_facts           = false
```

## Bugs and regression tests

No Mari Kit library bug blocked this workflow. Every failure path below is a
deliberate, documented contract, so it is asserted positively rather than
marked `xfail` or skipped:

- Unknown document citations raise `MalformedModelOutput`; there is no silent
  fallback.
- An invented quote raises `MalformedModelOutput`.
- A decisive verdict with an unverifiable quote is downgraded to `uncertain`
  with an explanatory suffix, preserving valid rows in the same batch.
- A missing source and a removed section produce `FreshnessStatus.MISSING`.
- Repeated extraction returns no new candidates.

One ergonomics issue was observed but is not a functional bug: when an evidence
row supplies a `section_id` that does not exist (or is the wrong heading path,
for example `b` instead of `a/b` for a nested heading), the raised message is
`evidence quote is not present in the requested section` rather than naming the
unknown section ID. A future message could distinguish "unknown section" from
"quote absent from the named section".

## API gaps

1. **No fact-level authorization.** `FactCandidate.evidence` carries document
   IDs but no ACL. Serving facts per principal requires the host to filter by
   `document_id`. This matches Mari's stated boundary, but onboarding/support
   consumers repeatedly need a shared helper; the example adds a local
   `serve_facts(facts, allowed_document_ids)`.
2. **No `apply_refinement` helper.** `parse_refinement` validates proposals but
   never mutates the source. The host must apply the exact replacement; the
   example does this to build handbook v2. This is intentional, but the
   host-side `str.replace` is an easily misused boundary.
3. **Checkpoint keys are structural.** `pending_fact_sections` keys on
   `(document_id, section_id)`. Renaming a heading while leaving its body
   identical forces re-extraction because the section ID changes. This is
   conservative and safe, not incorrect.
4. **No removal signal for deleted documents.** A retired document's section
   checkpoints simply stop matching; cleanup is left to the host.

## Host responsibilities vs. library behavior

The library deterministically validates citations, recomputes spans, binds
section revisions, and enforces an `allowed_document_ids` filter before
retrieval scoring. The example keeps these concerns in the host:

- principal-to-document authorization (`host_allowed_document_ids`),
- fact serving by authorized evidence (`serve_facts`),
- applying a reviewed policy edit to produce the next revision,
- persisting section checkpoints only after extraction commits.

## Remaining limitations

- All model output is a fixed fixture; no LLM, embedding service, or connector
  is exercised. Semantic support beyond exact quotation is out of scope.
- The corpus is three small documents; results are behavioral checks, not
  production-scale retrieval or extraction quality measurements.
- The combined `python -m examples.company_brains` runner currently stops in a
  different agent's `support.py` scenario. That failure is unrelated to this
  module; `python -m examples.company_brains.onboarding` runs cleanly.
