> Integration note: this is the original agent report. Findings and intermediate failures below are historical; see [the integrated report](README.md) for final fixes and verification.

# Conversation-Derived Company Brain — Build Report

## Deliverables

| File | Purpose |
| --- | --- |
| `examples/company_brains/conversation.py` | Credential-free runnable module exposing `run() -> dict`; `python -m examples.company_brains.conversation` prints JSON. |
| `tests/test_company_brain_conversation.py` | Behavioral tests for extraction, caching, edits, authorization, retrieval, failure paths, plus one core-bug regression test. |
| `artifacts/company-brains/conversation.md` | This report. |

The module turns a small multi-thread company conversation into revision-bound
episodes and extracts evidence-linked knowledge with a deterministic fixture
model. It uses only public Mari Kit APIs:

`KnowledgeEvent`, `segment_conversations`, `extraction_request`,
`compile_episodes`, `resolve_evidence`, `parse_episode_knowledge`,
`evidence_context`, `merge_chunk_knowledge`, `split_for_output`,
`topic_history`, `EpisodeKnowledge`, and the retrieval surface
`RevisionBM25Index` / `ArtifactRef.to_revision_ref`.

No model client, network, credentials, storage, or provider SDKs are used. The
callback is a pure function of the extraction request; embeddings/vector search
are out of scope for this source-evidence brain.

## Build outcome

`run()` produces four episodes (refund decision, checkout failure + lesson,
batch-scheduler open question, restricted failover note) and exercises the whole
lifecycle:

| Capability | Observed result |
| --- | --- |
| Extraction | 4 settled episodes, 4 model calls, 4 artifacts (`resolve=True`). |
| Evidence repair | Fixture omits offsets; resolver recomputes exact spans. One fabricated claim (`"Refunds are settled in five business days."`) is dropped as `quote-not-found`. |
| Caching | Second pass over the same episodes: `second_calls = 0`, `second_reused = 4` (no model call). |
| Edit invalidation | Edited `r1` (`revision="v2"`) re-segments to the *same* `episode_id` with a new `episode.revision`; cache key changes; recompile calls the model once and reuses the other 3. |
| Authorization | `evidence_context` fails closed on a stale artifact, a deleted event, and a revoked viewer; succeeds for a viewer with the `sre` entitlement. |
| Retrieval of evidence | BM25 over `retrieval_units()` facets, fused by episode id, then `evidence_context` resolves original quotes. The restricted episode is absent for the unauthorized viewer and present with `us-west-2-warm` for `sre`. |
| Failure recovery | `compile_episodes(..., retries=1, fail_fast=False)` on a contract-violating callback records `attempts=2` and `reason="invalid episode knowledge or source evidence"` instead of raising. |

`test_claims_are_bound_to_exact_source_spans` re-derives every `start:end`
slice from the returned quote, so every claim in the report is bound to the
current source revision.

## Bugs

### Library bug: `resolve_evidence` drops quotes whose ellipsis-separated parts are all short

`resolve_evidence` documents that it "splits quotes on `...`" and locates each
part. In `_resolve_claim_evidence`
(`src/mari_kit/conversation_knowledge.py`):

```python
parts = [p.strip() for p in _ELLIPSIS.split(quote)]
parts = [p for p in parts if len(p) >= _MINIMUM_PART] or [quote]
```

When the quote has an ellipsis but every resulting part is shorter than
`_MINIMUM_PART` (12), the filter empties the list and the `or [quote]` fallback
restores the *unsplit* quote — which still contains the ellipsis marker. That
literal can never occur in a source event, so the claim is reported
`quote-not-found` even though both fragments exist verbatim in the named event.

Reproduction with a real company event
(`"Enterprise refunds should stay at 30 days; ... legal reviewed ..."`) and the
loose model quote `"refunds [...] legal"`:

```text
resolve_evidence(episode, {"claims": [{"text": "...", "kind": "summary",
  "status": "explicit", "evidence": [{"quote": "refunds [...] legal"}]}]})
# -> ResolvedOutput(dropped=(DroppedClaim(reason="quote-not-found"),), ...)
# expected: two spans quoting "refunds" and "legal"
```

Exposed by
`tests/test_company_brain_conversation.py::test_resolve_locates_short_ellipsis_fragments_regression`
(fails until fixed; no `xfail`, no weakened assertion).

Suggested core fix in `_resolve_claim_evidence`: keep the short split parts when
the quote was actually split, and only use the whole-quote fallback for
un-split short quotes:

```python
parts = [p.strip() for p in _ELLIPSIS.split(quote)]
if _ELLIPSIS.search(quote):
    parts = [p for p in parts if p] or [quote]
else:
    parts = [p for p in parts if len(p) >= _MINIMUM_PART] or [quote]
```

This is a library bug, not a host bug: the resolver is library code and the
host supplied only the documented loose model output. It does not block this
build's primary workflow (the fixture never emits all-short ellipsis quotes),
which is why the test is a single intentionally failing regression rather than a
change to the example.

## API gaps

1. `compile_episodes` does not expose `lens` / `kinds`, although
   `extraction_request` supports them. A host that wants a lensed or
   kind-restricted extraction cannot use `compile_episodes`' cache, settling,
   and budget controls without rebuilding the request and caching itself.
   Suggested: accept `lens`/`kinds` and fold them into the cache key (or require
   `recipe` to encode them, as the docs already imply).
2. `EpisodeKnowledge.retrieval_units()` renders the scope as a metadata string
   and leaves `ArtifactRef.scope` empty, so a ref-keyed `RevisionBM25Index`
   cannot partition by `ScopeRef` from the unit ref alone; the host must carry
   scope separately. This matches the documented "scope metadata is for
   filtering" contract but is a small integration wrinkle for multi-tenant
   indexes.
3. The `resolve` flag is not part of the cache key. Reusing a strict artifact
   for a later `resolve=True` compile is correct (strict output is a subset of
   resolved output) but silently omits `dropped` observability for the reused
   episode.
4. There is no library-side facet/index pruning after an edit, split, or
   delete; `run()` rebuilds the index, and production hosts must remove stale
   facets themselves. This is explicitly a host responsibility in the docs.

## Host responsibilities vs library responsibilities

| Host (this example) | Library (Mari Kit) |
| --- | --- |
| Normalize messages, resolve edits/deletions, assign scope/stream/thread | Revision-bound `KnowledgeEpisode` identity and membership digest |
| Decide settling window and call budget | `compile_episodes` deferral, budget, retry, and cache reuse |
| Supply the JSON-producing model callback | `extraction_request` contract and `parse_episode_knowledge` provenance validation |
| Report model leniency (or run `resolve=True`) | `resolve_evidence` alias mapping, span recomputation, drop reporting |
| Own per-event clearance and `allowed` predicate | `evidence_context` fail-closed revision/authorization verification |
| Build/persist the retrieval index and prune stale facets | `RetrievalUnit`/`ArtifactRef` projection and ref-keyed BM25 search |
| Fuse facet hits by episode id (three facets are one source) | — (facets are ordinary `RetrievalUnit`s) |
| Model/provider versions in `recipe` | Cache key over membership + revision + recipe |

## Commands and results

```text
$ .venv/bin/ruff format examples/company_brains/conversation.py tests/test_company_brain_conversation.py
2 files left unchanged

$ .venv/bin/ruff check examples/company_brains/conversation.py tests/test_company_brain_conversation.py
All checks passed!

$ .venv/bin/python -m examples.company_brains.conversation
{ ... 8151-byte JSON report; extraction.episode_count = 4, cache.second_reused = 4 ... }
exit=0

$ .venv/bin/python -m pytest tests/test_company_brain_conversation.py -q
1 failed, 16 passed in 0.17s

$ .venv/bin/python -m pytest tests/test_conversation_knowledge.py -q
28 passed in 0.15s
```

The single failure is the intentional core-bug regression test above. All 16
other behavioral and failure-path tests pass, and the pre-existing
`conversation_knowledge` suite is unaffected.

## Remaining limitations

- The dataset is four small threads and the model callback is a fixture. It
  demonstrates the contracts, not extraction or retrieval quality; no semantic
  benchmark is claimed.
- Retrieval is lexical BM25 over summary/question/topic facets. It demonstrates
  "match vocabulary absent from source", not embedding-quality recall.
- The pipeline is in-memory and rebuilt per `run()`; no durable queue, cache
  store, or index persistence is shown, which is correct for a deterministic,
  credential-free example.
- Authorization is modeled as an event-level clearance map owned by the host.
  The library provides the fail-closed check, not an ACL implementation.
- The `resolve_evidence` short-ellipsis defect remains open and its regression
  test fails by design until the suggested one-line-branch fix lands.
- Note: the working tree also contains a concurrent core fix to
  `RevisionBM25Index` tie-break padding (a 12-unit index is past the ten-unit
  boundary). This example's assertions do not depend on tie order, so they hold
  with or without that fix.
- I modified only `examples/company_brains/conversation.py`,
  `tests/test_company_brain_conversation.py`, and
  `artifacts/company-brains/conversation.md`; no other files, git state,
  configuration, or credentials were touched.
