> Integration note: this is the original agent report. Findings and intermediate failures below are historical; see [the integrated report](README.md) for final fixes and verification.

# Company Brain: Cross-Source Search

Build report for the search scenario in `examples/company_brains/`.

## Deliverables

| Artifact | Purpose |
|---|---|
| `examples/company_brains/search.py` | Credential-free runnable module: `run() -> dict` plus a `__main__` that prints JSON. |
| `tests/test_company_brain_search.py` | 12 behavioral tests, including empty-authorization, stale-revision, CAS, edit, and deletion failure paths. |
| `artifacts/company-brains/search.md` | This report. |

Only these three files were authored. `examples/company_brains/__init__.py`,
`examples/company_brains/__main__.py`, and the sibling scenario modules are
owned by other concurrent agents.

## Build outcome

Working. The module composes real Mari Kit APIs and needs no credentials,
network, model, database, or scheduler:

- **Cross-source corpus.** Three provider sources (`handbook`, `slack`,
  `github:acme/runbooks`) are committed into one `RevisionBM25Index`.
- **Scoped revision storage.** `InMemoryDocumentStore` is keyed by
  `ScopeRef(tenant="acme", space="company")`. Same tenant/external identity in a
  different scope keeps independent revisions.
- **Host-owned authorization.** `host_allowed_refs()` maps observed
  `DocumentACL` principals and caller `Principal`s to a `frozenset[RevisionRef]`.
  Mari records visibility but never authorizes; the host supplies the set to
  `RevisionBM25Index.search(allowed_refs=...)`.
- **Exact cited answers.** `parse_answer` validates an extractive quote against
  the authorized document and returns evidence with `document_id`, `revision`,
  `section_id`, and character span. A fabricated quote raises
  `MalformedModelOutput`.
- **Edits.** A new `handbook-v2` revision is committed with
  `expected_revision="handbook-v1"` (compare-and-swap). A concurrent writer
  based on the stale `v1` is rejected with `RevisionConflict`.
- **Deletions.** A host tombstone removes the live revision; retrieval drops it,
  while `InMemoryDocumentStore.history()` still returns `slack-v1`.

Observed result of `python -m examples.company_brains.search` (trimmed):

```json
{
  "sources": ["github:acme/runbooks", "handbook", "slack"],
  "authorization": {
    "outsider_allowed": [],
    "unauthorized_match_excluded": true
  },
  "retrieval": {
    "support_hits": ["slack/thread:refund-1042@slack-v1", "handbook/refunds@handbook-v1"],
    "finance_hits": ["github:acme%2Frunbooks/billing.md@github-v1", "handbook/refunds@handbook-v1"],
    "outsider_hits": []
  },
  "answers": {
    "refund": {
      "disposition": "grounded",
      "grounding_coverage": 0.9,
      "citations": [{
        "document_id": "handbook/refunds",
        "revision": "handbook-v1",
        "section_id": "root",
        "quote": "Enterprise refund window: purchases can be refunded within 30 days of invoice."
      }]
    },
    "outsider": {"disposition": "insufficient_evidence", "citations": []}
  },
  "edit": {
    "stale_commit_rejected": true,
    "stale_commit_error": "expected 'handbook-v1', found 'handbook-v2'",
    "cached_answer_freshness": "stale",
    "answer_after_edit": [{"revision": "handbook-v2",
      "quote": "Enterprise refund window: purchases can be refunded within 45 days of invoice."}]
  },
  "deletion": {
    "hits_after_delete": ["handbook/refunds@handbook-v2"],
    "cached_answer_freshness": "missing",
    "history_revisions": ["slack-v1"]
  }
}
```

### Exercised behaviors

| Requirement | Where | Result |
|---|---|---|
| Cross-source retrieval | `test_support_and_finance_retrieve_different_cross_source_revisions` | Support sees `{handbook, slack}`; finance sees `{handbook, github}`. |
| Scoped revision storage | `test_scope_isolation_keeps_tenant_revisions_separate` | `acme` at `handbook-v2` does not change `beta` at `handbook-v1`. |
| Host authorization before scoring | `test_unauthorized_matching_document_is_filtered_before_scoring` | `explain()` proves the unauthorized GitHub doc matches the query (`score > 0`), yet it never appears in support hits. |
| Empty authorization | `test_empty_authorization_returns_no_hits_or_citations` | `allowed_refs=frozenset()`; search `()`, answer `insufficient_evidence`, no citations. |
| Stale revision (CAS) | `test_stale_revision_commit_is_rejected_by_compare_and_swap` | `RevisionConflict`, current stays `handbook-v2`. |
| Stale revision (freshness) | `test_edit_invalidates_cached_answer_and_old_retrieval_ref` | `assess_freshness` → `STALE`, `reusable=False`; old ref absent from the rebuilt index. |
| Deletion | `test_deletion_drops_live_revision_and_retains_history` | Search drops Slack; freshness → `MISSING`; history retains `slack-v1`. |
| Exact-citation rejection | `test_fabricated_citation_is_rejected` | `MalformedModelOutput`. |
| Off-topic abstention | `test_off_topic_question_abstains_even_with_authorized_documents` | Zero-score authorized docs do not produce a grounded answer. |
| JSON result contract | `test_run_is_json_serializable_and_exercises_every_path` | `json.dumps(run())` succeeds. |

## Host responsibilities vs library boundaries

These are host-owned by design and are implemented in the example rather than
delegated to Mari:

- **Authorization policy.** `DocumentACL` is provider-observed metadata. Mapping
  it to allowed `RevisionRef`s, and treating `public`/`connector_scope` as
  tenant-visible, is application policy.
- **Answer generation.** The example uses a deterministic extractive quote. A
  production host substitutes a model call and still validates the result with
  `parse_answer`.
- **Deletion/tombstones.** Mari's sync transaction protocol has `delete`, but the
  document-store reference implementations do not expose a delete method.
  Applying a tombstone to a live view and retaining governed history is host
  storage work.
- **Index refresh.** `RevisionBM25Index` is immutable. The host rebuilds the
  mapping after a commit or delete.

## API gaps

No gap blocked the required workflow. These are the friction points found, in
priority order.

1. **`RevisionBM25Index` has no `with_deltas()`.** `BM25Index` and
   `ArtifactBM25Index` both support revision-checked incremental updates, but the
   structural-revision adapter the permission-aware examples use does not. Every
   edit or delete forces a full index rebuild, and there is no public
   `RevisionIndexDelta`. This is the clearest structural asymmetry in
   `src/mari_kit/retrieval/indexes.py`.
   *Suggested core fix:* add a `RevisionIndexDelta(ref, operation, text,
   previous_ref)` value mirroring `ArtifactIndexDelta`, and a
   `RevisionBM25Index.with_deltas()` that applies upserts/deletes into the unit
   mapping and returns a new snapshot (with the same revision checks).
2. **BM25 corpus statistics are not authorization-scoped.** `BM25Index.__init__`
   computes IDF over every indexed document, while `search()` filters scoring to
   `allowed_document_ids`. Restricted documents never appear in results, but
   their terms still affect the IDF of authorized documents, so scores (and
   `explain()`) can reveal whether a term exists in an unauthorized document.
   *Suggested direction:* either document this as a known property of
   post-filter lexical retrieval, or offer a scoped-statistics search that
   recomputes corpus statistics from the allowed subset before scoring.
3. **`search()` returns zero-score documents.** Every authorized document is
   returned regardless of lexical match, so a rank `limit` is not a relevance
   filter. The example guards with `hit.score > 0.0` before answering. A
   `min_score` parameter or documented host-side threshold would make this
   explicit.
4. **No scoped delete on `DocumentStore`.** `InMemoryDocumentStore` exposes
   `commit`/`get`/`resolve`/`history` only; deletion semantics live in the sync
   transaction protocol. This is defensible separation, but the example must
   maintain a separate live-document mapping.

## Bugs

No library bug prevented a valid workflow, so no regression test was added to
the shared suite (which is outside this task's owned files anyway). All
failure-path tests in `tests/test_company_brain_search.py` pass against the
current API. The items above are gaps and design notes, not defects.

The only correctness edge found is by-design library behavior handled by host
code: zero-score hits are treated as non-answers in `CompanyBrain.answer`, and
the off-topic test locks that behavior in.

## Commands and results

Run from `/Users/henneberger/mari-kit`:

```text
$ .venv/bin/python -m examples.company_brains.search
<prints the JSON summary above>

$ .venv/bin/python -m pytest tests/test_company_brain_search.py -q
............                                                             [100%]
12 passed in 0.15s

$ .venv/bin/ruff format examples/company_brains/search.py tests/test_company_brain_search.py
2 files left unchanged

$ .venv/bin/ruff check examples/company_brains/search.py tests/test_company_brain_search.py
All checks passed!
```

## Remaining limitations

- The corpus is a small deterministic fixture; no benchmark or relevance-quality
  claim is made.
- The extractive answerer quotes the top positive-scoring authorized document.
  Without a `min_score` boundary from the library it cannot distinguish
  "weakly related" from "strongly relevant" beyond `score > 0`.
- Authorization is static per query. ACL revocation mid-session, principal
  hierarchies, and group expansion are not modeled.
- Deletion is a host tombstone over the live view; the reference store keeps
  history, so a host that wants hard deletion must implement it in its own
  storage adapter.
- Section-level freshness (`current_section_revisions`) is not exercised because
  the fixture documents are single-section; the citation does carry `section_id`
  and `section_revision`, so the finer check is available to hosts.
