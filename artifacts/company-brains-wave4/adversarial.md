> Agent handoff report. See [integrated results](README.md) for coordinator fixes, final measurements, and supported behavior.

# Wave 4: durable auth/cache lifecycle, adversarial host report

Owner: `adversarial` test agent. Owned files:

- `tests/test_brain4_adversarial.py` (new, 26 tests)
- `artifacts/company-brains-wave4/adversarial.md` (this report)

No source file, dependency, credential, network access, other agent's file, or
git state was modified. `engine.py`, `store.py`, and the sparse-index code are
owned by other wave-4 agents and were only read (and observed to change during
this run).

## What was built

`tests/test_brain4_adversarial.py` attacks the durable company-brain from the
host side. It fixes two independent oracles and compares the live engine against
them:

1. **Fresh authorized read + exact BM25.** `_oracle_hits` opens the same SQLite
   file, reads documents and groups from a consistent snapshot, re-applies the
   host ACL policy in a second, independent implementation (`_host_allowed`),
   and ranks with `_exact_bm25_ranking`, a local reimplementation of
   Robertson--Walker BM25 including the reference index's padded-position
   tie-breaking. `test_independent_oracle_matches_fresh_library_index` asserts
   this oracle equals a freshly built `RevisionBM25Index`, so the oracle itself
   is pinned.
2. **Request identity / record shape.** The persisted cache key is re-derived
   independently (`_cache_key`) and forged records are injected through the
   store's public `save_cache`, optionally after recomputing the engine's
   unkeyed checksum (`seal_cache_record`) to model a writer that re-seals.

Coverage beyond the earlier waves:

- **Deterministic randomized lifecycle.** Seeds `1, 7, 13, 42, 99`, 90 steps
  each, over a writer connection, a reader connection, and a third oracle
  connection; two scopes; three users; nine operation classes: body revision,
  same-revision title, same-revision ACL, delete, add, membership change, a
  rollback injected with `apply_plan(failpoint=...)`, a change in the *other*
  scope, and a store restart. After every step, for every scope/user/query, the
  engine's `search` must equal the oracle, its `answer` disposition must match,
  and its grounded evidence must cite the oracle's top document.
- **Mutable scope changes *during* generation.** A callback reassigns
  `brain.scope` while `answer` is running; separate tests switch to another
  populated scope and to an empty scope.
- **Corrupted/misbound persisted records.** Wrong question, wrong user, wrong
  schema, wrong scope, missing fingerprint, non-mapping `dependencies`/`evidence`
  entries, grounded-without-evidence, invalid disposition, wrong evidence
  revision, and accidentally corrupted answer text.
- **Cache-budget eviction.** `view_cache_bytes` of `1` (constant eviction) and
  `None`, verified against the oracle across body/ACL/membership steps.

## Result summary

| Revision | `engine.py` sha256 (prefix) | schema | Outcome |
| --- | --- | --- | --- |
| wave-4 start | `ca5fb794…` | v1 | **11 of the cache tests failed** (8 bug classes below) |
| final validation | `80c94d43…` | v2 + `cache_records.py` | **26/26 pass**, randomized/scope/isolation/rollback all pass |

Run:

```bash
.venv/bin/ruff check tests/test_brain4_adversarial.py          # All checks passed
.venv/bin/ruff format --check tests/test_brain4_adversarial.py # already formatted
.venv/bin/python -m pytest tests/test_brain4_adversarial.py -q # 26 passed
.venv/bin/python -m pytest tests/test_brain4_adversarial.py \
  tests/test_brain3_cache.py tests/test_brain2_engine.py \
  tests/test_brain2_revocation.py tests/test_brain3_integration.py \
  tests/test_brain3_recall.py -q                               # 89 passed
```

## Bugs found against the wave-4 start revision (`ca5fb794`, schema v1)

All observations below were reproduced with a host-forged record saved through
`SQLiteBrainStore.save_cache`; the pre-fix `_serve_cached` checked only the
schema, the authorized fingerprint, dependencies, and the evidence *quote
substring*. The exact pre-fix code lived in `engine.py`'s `_serve_cached`
(roughly lines 382-407 of that revision).

| ID | Regression test | Pre-fix observed | Desired behavior |
| --- | --- | --- | --- |
| W4-01 | `test_mismatched_question_record_is_not_served` | A record stored under `(question, user)` whose payload `question` differs is served: `cache_hit=True`, `answer='WRONG-Q'`. | Reject the record (regenerate). |
| W4-02 | `test_mismatched_user_record_is_not_served` | Same with a different `user_id`: `cache_hit=True`, `answer='WRONG-U'`. | Reject the record. |
| W4-03 | `test_missing_fingerprint_record_is_not_served` | A record with no `authorized_fingerprint` matches an empty authorized set (`[] == []`) and is served: `cache_hit=True`, `answer='FORGED-NO-FINGERPRINT'`, `disposition='grounded'`, `evidence=[]`. | Require a fingerprint field of the right type. |
| W4-04 | `test_malformed_record_entries_are_a_cache_miss[dependencies-*]` | `dependencies=["not-a-mapping"]` or `[42]` raises `AttributeError: 'str'/'int' object has no attribute 'get'` from `engine.py:614` instead of treating the record as a miss. A corrupted row can crash every `answer` for that key. | Malformed record is a cache miss (no exception). |
| W4-05 | `test_malformed_record_entries_are_a_cache_miss[evidence-*]` | `evidence=["not-a-mapping"]` or `[17]` raises `AttributeError` from `engine.py:622`. | Malformed record is a cache miss. |
| W4-06 | `test_grounded_record_without_evidence_is_not_served` | A record with `disposition='grounded'`, `evidence=[]`, `dependencies=[]` is served: `cache_hit=True`, `answer='GROUNDED-WITHOUT-EVIDENCE'`. This violates the engine's own `GroundedAnswer` "grounded requires evidence" invariant. | Reject grounded records with no evidence/dependencies. |
| W4-07 | `test_invalid_cached_disposition_is_not_served` | `disposition='totally-bogus'` is passed straight to the caller (`_present` stringifies it). | Reject unknown dispositions. |
| W4-08 | `test_wrong_evidence_revision_is_not_served` | Evidence rows are checked only for `document_id` and a quote substring; an evidence `revision` of `"r999"` on the current `"r1"` document is served. | Compare the evidence revision to the live document. |
| W4-09 | `test_accidentally_corrupted_answer_field_is_not_served` | With the record otherwise valid, `answer='The Nimbus launch code is hunter2.'` is served while the evidence still quotes the policy: `cache_hit=True`. `_serve_cached` never validates the answer text. | Do not serve accidentally corrupted answer text. |

The pre-fix evidence, captured directly from the engine:

```text
wrong_question:            disposition='grounded' cache_hit=True answer='WRONG-Q'
wrong_user:                disposition='grounded' cache_hit=True answer='WRONG-U'
malformed_dependency:      RAISED AttributeError: 'str' object has no attribute 'get'
malformed_evidence:        RAISED AttributeError: 'int' object has no attribute 'get'
grounded_without_evidence: disposition='grounded' cache_hit=True answer='NO-EVIDENCE' evidence_len=0
invalid_disposition:       disposition='totally-bogus' cache_hit=True
wrong_evidence_revision:   disposition='grounded' cache_hit=True (evidence revision r999)
ungrounded_answer:         disposition='grounded' cache_hit=True answer='UNGROUNDED-SECRET'
missing_fingerprint:       disposition='grounded' cache_hit=True answer='FORGED-NO-FINGERPRINT' evidence_len=0
```

## Fix verification

While this report was being written, the engine owner added
`examples/company_brains/durable/cache_records.py` and bumped the cache schema
to `company-brain-answer-v2`. `_serve_cached` now calls
`cache_record_matches_request`, which validates:

- `schema`, `question`, `user_id`, and `scope_key` against the live request;
- that `answer` is a non-empty string;
- an unkeyed SHA-256 `checksum` over canonical JSON;
- a valid `disposition`;
- `authorized_fingerprint` is a list of strings;
- `evidence` and `dependencies` are lists of mappings with the required string
  fields and consistent `start`/`end` types;
- the evidence `(document_id, revision)` set equals the dependency set;
- grounded records require evidence; abstentions require no dependencies.

All eleven previously failing tests now pass. To ensure they exercise the
*structural* validator rather than only the checksum, every forged record in the
suite is re-sealed with `seal_cache_record` before being stored (except the
accidental-corruption answer test, which intentionally leaves the checksum
broken). A new `test_mismatched_scope_record_is_not_served` additionally verifies
that a re-sealed record bound to scope A is rejected when loaded for scope B even
though both scopes have byte-identical documents.

## Verified non-findings (desired behavior holds)

- The randomized lifecycle never diverged from the fresh oracle across five
  seeds and 90 steps: search results, answer dispositions, and top evidence
  documents all matched, including after restarts and injected rollbacks.
- Scope changes during generation never served the old scope's prose. The
  returned content belonged to the scope live at serve time, the persisted
  record was attributed to that scope, and a switch to an empty scope produced a
  non-cached abstention.
- Rollback left document state and both epochs unchanged (no phantom
  invalidation, no stale serving afterwards).
- Two-connection edits, same-revision ACL moves, membership grants/revocations,
  and deletions always invalidated the memoized view and the persisted answer.
- Byte-budget eviction (`view_cache_bytes=1`, i.e. eviction on every store) never
  served stale content.
- Cross-scope and cross-user isolation held: neither scope/user could retrieve
  the other's documents or answer prose.

## Residual risks and limits (not fixed, not authentication bugs)

These were probed and are reported for completeness. They require a writer that
can execute `seal_cache_record`, which the module explicitly places outside its
trust model ("not authentication"; "the database and cache-writing application
remain trusted").

1. **The checksum is unkeyed.** Anyone who can write the cache file can
   recompute it for an arbitrary record. A re-sealed record whose `answer` text
   is unrelated to its (valid) evidence is served with `cache_hit=True`
   (`RESEALED-SEMANTIC-POISON`). `cache_record_matches_request` deliberately does
   not check the semantic truth of cached prose.
2. **A re-sealed abstention with evidence is accepted.** `disposition =
   insufficient_evidence` plus valid, non-empty evidence and dependencies passes
   the validator and is returned as an abstention that still carries evidence.
   Under the accidental-corruption model the checksum catches this; under a
   re-sealing writer it is an internal-consistency inconsistency, not a leak.
3. **Cache integrity is per-record, not authenticated.** Protecting against a
   malicious host/cache writer would require a keyed MAC or an authority check,
   which is out of scope for this example.

## Reproduce

```bash
.venv/bin/python -m pytest tests/test_brain4_adversarial.py -q
.venv/bin/ruff check tests/test_brain4_adversarial.py
.venv/bin/ruff format --check tests/test_brain4_adversarial.py
```

Hashes at final validation:

```text
engine.py       80c94d434cee8358e823fa7eae95e0faf75a0a9f8487c06243426f9efa9bbedd
store.py        7175b31c72d8c4065c7e4ae310a82b3e230786b6853e26967aaa7371a769dd1d
cache_records.py 31f048bb9bce02cf686173b2e27a5ebb3c8a7ff99bcf210e5bf9a1a7da41407a
test file       fa7e77fafabcff0cb48e130695f922cd500999c2ef0797eca9217952d65348ee
```

`engine.py` is concurrently owned and changed several times during this run
(`ca5fb794…` → `e32bc727…` → `80c94d43…`); line numbers in the pre-fix table are
from `ca5fb794` and may not match later revisions.
