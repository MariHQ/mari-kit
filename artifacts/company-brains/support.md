> Integration note: this is the original agent report. Findings and intermediate failures below are historical; see [the integrated report](README.md) for final fixes and verification.

# Customer Support Company Brain — Build Report

## Deliverables

| File | Purpose |
| --- | --- |
| `examples/company_brains/support.py` | Credential-free runnable module exposing `run() -> dict`; `python -m examples.company_brains.support` prints JSON. |
| `tests/test_company_brain_support.py` | Behavioral tests, host-boundary failure paths, and one core-bug regression test. |
| `artifacts/company-brains/support.md` | This report. |

The module builds a reviewed answer/workflow cache for a customer support
company brain and exercises seven scenarios: valid reuse, changed source,
unchanged-source/unrelated section edit, relevant new document, revoked access,
unanswered question, plus a cold reviewed intent and a below-threshold near
miss. It uses only public Mari Kit APIs:

`KnowledgeDocument`, `DocumentACL`, `Principal`,
`parse_answer`, `KnowledgeDependency`, `impacted_artifacts`, `section_revisions`,
`ReviewedWorkflow`, `build_reviewed_workflow_index`, `WorkflowPolicy`,
`match_cached_response`, `decide_reviewed_workflow`, `start_speculative_retrieval`.

No model client, network, credentials, or storage are used. Embeddings are a
host responsibility, so the module supplies fixed deterministic intent vectors
rather than claiming to be an embedding model.

## Build outcome

All seven required scenarios behave as designed.

| Scenario | Action | Reason | Key result |
| --- | --- | --- | --- |
| Valid reuse | `cached_response` | `exact_fresh_cache` | score `1.0`, served reviewed 30-day answer |
| Changed cited source | `speculative_retrieval` | `stale_dependency` | only `workflow:support-refund` impacted; shipping still cached |
| Changed context voice | `speculative_retrieval` | `stale_dependency` | non-factual context dependency also invalidates |
| Unrelated section edit | `cached_response` | `exact_fresh_cache` | section revisions preserve reuse; whole-document fallback is stale |
| Relevant new document | unresolved `speculative_retrieval` / `relevant_document_needs_impact_review`; non-impacting `cached_response`; impacting `speculative_retrieval` / `relevant_document_impacts_response` | reviewed impact clears or forces the LLM |
| Revoked access | `llm` | `no_intent_match` | restricted dependency is filtered; no cached answer returned |
| Unanswered question | `llm` | `no_intent_match` | no reviewed intent |
| Cold reviewed intent | `speculative_retrieval` | `no_cached_response` | password reset has no reviewed answer yet |
| Below-threshold near miss | `speculative_retrieval` | `below_cache_threshold` | score `0.957`, between `0.70` and `0.97` |

`start_speculative_retrieval` genuinely starts an `asyncio.Task` before it is
awaited (`started_before_await: true`) and reads the workflow's document
dependencies.

## Bugs

### Core bug: `decide_reviewed_workflow` abandons an available fresh reviewed cache

`match_cached_response` and `decide_reviewed_workflow` disagree on identical
inputs. When two reviewed versions of one intent share a document and the
higher-scoring (exact) workflow is stale while a lower-scoring (near) workflow
is fresh:

- `match_cached_response(..., minimum_score=cache_threshold)` returns
  `HIT` for the fresh workflow (`refund-v2`).
- `decide_reviewed_workflow(..., policy=WorkflowPolicy())` returns
  `SPECULATIVE_RETRIEVAL` / `stale_dependency` for the stale workflow
  (`refund-v1`) and never considers the fresh cache.

Both receive the same index, revisions, and query, so a host cannot rely on the
documented primary entry point to reuse an answer the library's own cache
matcher considers reusable. The broader suite already asserts the intended
semantics for `match_cached_response`
(`test_reviewed_cache_skips_stale_higher_scoring_workflow`), which makes the
`decide_reviewed_workflow` behavior inconsistent rather than merely conservative.

Exposed by
`tests/test_company_brain_support.py::ReviewedCacheConsistencyRegressionTests::test_fresh_reviewed_cache_is_not_shadowed_by_a_stale_exact_match`
(fails, by design, until fixed; no `xfail`, no weakened assertion).

Suggested core fix, in `src/mari_kit/trajectories/workflows.py`
`decide_reviewed_workflow`: when the top intent match is not reusable because of
freshness, fall back to the fresh-cache selection before returning
`SPECULATIVE_RETRIEVAL`. Concretely, when `not freshness.reusable` (and no
unresolved/impacting relevant document applies), call the same logic used by
`match_cached_response` for this query/revisions/sections/authorization with
`minimum_score=cache_threshold`; if it returns a `HIT`, return
`CACHED_RESPONSE` with that match's workflow, otherwise continue as today.
`match_cached_response` already implements the required "highest-scoring fresh
cached response" scan, so the fix is to reuse it rather than to duplicate it.

This is a library bug, not a host bug: the host supplies a valid index and
current revisions and follows the README's `decide_reviewed_workflow` path.

## API gaps

1. `match_cached_response` reports `CacheDecisionReason.BELOW_THRESHOLD` when a
   matching workflow was excluded solely by `allowed_document_ids`. The
   revocation in this build surfaces as `below_threshold`, not an authorization
   reason. Reusability is still correctly `False`, so this is an observability
   gap: hosts must intersect with their own authorization decision to explain
   the miss.
2. There is no first-class "reviewed answer version/supersession" concept.
   Hosts must model a corrected cached answer as a separate `ReviewedWorkflow`
   and rebuild the index. That modeling choice is exactly what triggers the core
   bug above.
3. `decide_reviewed_workflow` only inspects the single highest-scoring intent.
   There is no parameter to prefer a fresh lower-ranked reviewed workflow, so
   the two cache entry points have different selection semantics.
4. Query and relevance embeddings/scores remain host inputs
   (`query_vectors`, `relevant_document_scores`), as documented. There is no
   library helper to derive relevance from a document index, which is correct
   but means the "new relevant document" gate is only as good as the host's
   scores.

## Host responsibilities vs library responsibilities

| Host (this example) | Library (Mari Kit) |
| --- | --- |
| Documents, revisions, provider ACL observations | Reviewed-intent MUVERA index and exact MaxSim ranking |
| Mapping principals to `allowed_document_ids` | Excluding workflows with unauthorized dependencies |
| Query embeddings and relevance scores | Cache gate and freshness decisions |
| The actual agent/LLM answer round | Evidence/quote/revision validation (`parse_answer`) |
| Impact review decisions | Dependency change-impact reports |
| Persistence of reviewed answers and cache state | Section-level dependency freshness |

## Commands and results

```text
$ .venv/bin/ruff format examples/company_brains/support.py tests/test_company_brain_support.py
1 file reformatted, 1 file left unchanged

$ .venv/bin/ruff check examples/company_brains/support.py tests/test_company_brain_support.py
All checks passed!

$ .venv/bin/python -m examples.company_brains.support
{ ... full JSON result, valid_reuse.action = "cached_response" ... }

$ .venv/bin/python -m pytest tests/test_company_brain_support.py -q
1 failed, 17 passed in 0.25s
```

The single failure is the intentional core-bug regression test described above.
All other behavioral and failure-path tests pass.

## Remaining limitations

- The intent space is a fixed four-dimensional unit-vector stub. A production
  brain must supply a real embedding model and validate the `0.70` / `0.97`
  thresholds against its score distribution.
- Relevance for the new document is injected by the host
  (`relevant_document_scores={new_document_id: 0.99}`); the example does not run
  retrieval to discover it.
- Nothing is persisted between `run()` calls; the index and reviewed answers are
  rebuilt in memory, which is appropriate for a deterministic example.
- The core bug remains open. The regression test fails until the suggested fix
  lands; it was not marked `expectedFailure` and no assertion was weakened.
- I did not modify any file, git state, configuration, or credentials outside
  the three owned paths.
