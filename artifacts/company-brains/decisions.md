# Company decision memory brain

Build report for `examples/company_brains/decisions.py`, its behavioral tests,
and this artifact. The brain parses proposed decisions, binds them to exact
source revisions, applies an explicit review policy, and re-reviews them after
source sections change.

## Build outcome

Delivered and green:

| Deliverable | Path |
|---|---|
| Runnable brain (`run() -> dict`, JSON `__main__`) | `examples/company_brains/decisions.py` |
| Behavioral tests (18) incl. failure paths | `tests/test_company_brain_decisions.py` |
| This report | `artifacts/company-brains/decisions.md` |

The module is credential-free and deterministic: it reads no environment, calls
no model, and uses no network. It is built entirely from public Mari Kit APIs:
`parse_decisions`, `section_revisions`, `assess_freshness`,
`validate_artifact_evidence`, `document_evidence_ref`, `KnowledgeArtifact`,
`Activity`, `ReviewState`, `evaluate_write`/`MemoryWrite`, and
`plan_memory_mutations`/`apply_memory_mutations`, with
`InMemoryArtifactStore` as the reference store.

What `run()` exercises end to end:

- **Four proposed decisions** from three documents: two exact handbook
  decisions (approved), one paraphrased decision below the grounding floor
  (rejected), and one decision whose only source is an untrusted,
  instruction-bearing web page (quarantined, held as a proposal).
- **Invalid citations** at both layers: five malformed model outputs rejected by
  `parse_decisions`, plus re-resolution that reports `unresolved`,
  `not_visible`, and `quote_mismatch`.
- **Revised evidence**: the retention section moves `d1 -> d2` while the
  deployment section is unchanged. Freshness marks only retention `stale`;
  a `MemoryDecision` UPDATE targets one stable decision identity, a NOOP reuses
  the other, and the artifact store supersedes `v1` with `v2`.
- **Explicit review policy** (`ReviewPolicy`, `_review`):
  1. missing/rejected provenance -> `REJECTED`
  2. stale evidence -> `PROPOSED` (needs re-extraction/re-review)
  3. grounding below `minimum_grounding` -> `REJECTED`
  4. quarantined provenance -> `PROPOSED`
  5. otherwise -> `APPROVED`

The policy collects every failed reason instead of short-circuiting, so an
audit sees all signals.

## Review policy and host responsibilities

Mari Kit owns the vocabulary and the deterministic signals; the host owns the
decision. This module keeps that split explicit.

| Concern | Owner |
|---|---|
| Evidence parsing, exact quote/revision binding | Library |
| `grounding_coverage` lexical score | Library |
| Freshness status (`current`/`stale`/`missing`/`unversioned`) | Library |
| Write boundary (provenance, untrusted instruction) | Library |
| Mutation-plan validation and application | Library |
| Artifact envelope, lineage, supersession, store semantics | Library |
| Source trust, interpretation, and taint mapping | Host |
| Review thresholds and state precedence | Host |
| Stable `decision_id` identity and scope/clock | Host |
| Section-revision map assembly and artifact commits | Host |
| Semantic entailment, authorization, persistence, scheduling | Host (absent here) |

## Commands and results

Run from `/Users/henneberger/mari-kit` with the project virtualenv.

| Command | Result |
|---|---|
| `.venv/bin/python examples/company_brains/decisions.py` | exit 0, `"passed": true` |
| `.venv/bin/python -m pytest tests/test_company_brain_decisions.py` | `18 passed` |
| `.venv/bin/ruff format examples/company_brains/decisions.py tests/test_company_brain_decisions.py` | `2 files reformatted` |
| `.venv/bin/ruff check examples/company_brains/decisions.py tests/test_company_brain_decisions.py` | `All checks passed!` |
| `.venv/bin/python -m pyright examples/company_brains/decisions.py tests/test_company_brain_decisions.py` | `0 errors, 0 warnings` |

Failure-path tests assert real exceptions rather than suppress them:
`MalformedModelOutput` for unknown documents, absent quotes, empty evidence,
missing statements, and non-array output; `reject` for missing provenance;
`quarantine` for untrusted instruction sources; `stale` for the revised
section; and `quote_mismatch` for a tampered quote.

## API gaps

These are seams a production host must bridge; none is blocking and none was
worked around by reimplementing an algorithm.

1. `parse_decisions` returns `DecisionCandidate` without caller metadata. A
   stable `decision_id` cannot ride on the candidate, so the host must zip the
   original rows with the returned tuple by position (order is preserved, but
   the contract is implicit). An optional id field surfaced on the candidate
   would make memory-store joins explicit.
2. `knowledge.facts._evidence` silently rebinds an unknown `document_id` to the
   only supplied document when the quote matches (`facts.py:52-55`). With one
   document, a fabricated source id is therefore repaired, not rejected;
   rejection requires two or more documents. This is defensible convenience but
   is not stated on the public parser docstrings, and it changes behavior with
   corpus size.
3. Two evidence types meet in a governed artifact: `KnowledgeArtifact.evidence`
   accepts the compatibility `Evidence | LocatedEvidence`, while the generic
   validator consumes `ArtifactEvidence` from `document_evidence_ref`. The host
   keeps both and must remember that artifact validation uses the generic path.
4. `assess_freshness` needs the host to assemble `section_revisions(documents)`;
   there is no combined "assess this evidence against these documents" entry
   point.
5. With `visible_refs` supplied, an out-of-date revision reports `not_visible`
   (filtered before resolution); without it, the same revision reports
   `unresolved`. Both are correct but the caller must choose deliberately.

## Bugs

No library bug blocked a valid workflow, so no regression test is warranted.
The one failure encountered during construction was in this module
(`document_evidence_ref(...).ref` is a scalar `ArtifactRef`, not an iterable)
and was fixed locally. Behaviors 2 and 5 above are documented API surprises,
not defects.

## Remaining limitations

- The model boundary is a deterministic fixture, not a live model; nothing here
  proves extraction quality. `grounding_coverage` is lexical overlap and is not
  entailment, confidence, or truth.
- The store is in-memory and single-tenant per process; there is no durability,
  concurrent write control, retrieval-time authorization, or scheduling.
- Freshness uses Markdown section revisions; heading-free prose falls back to
  whole-document revision, so unrelated edits can over-invalidate.
- Untrusted-source quarantine depends on host-declared trust, interpretation,
  and taints rather than content inference.
- `artifacts/company-brains/decisions.jsonl` was present before this build and
  appears to be an unrelated agent session capture. It is outside this
  deliverable and was left untouched.
