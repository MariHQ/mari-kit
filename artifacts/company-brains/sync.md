# Company brain: continuous synchronization

## Deliverables

| Path | Purpose |
| --- | --- |
| `examples/company_brains/sync.py` | Credential-free runnable module exposing `run() -> dict`; `python -m examples.company_brains.sync` prints JSON. |
| `tests/test_company_brain_sync.py` | 7 behavioral tests covering the happy path and failure paths. |
| `artifacts/company-brains/sync.md` | This report. |

Only these three paths were written. No other files, git state, configuration, or
credentials were touched.

## Build outcome

The module builds and runs green. A deterministic host (`CompanyBrain`)
synchronizes a fake provider (`CompanySource`) through the public Mari Kit
surface:

- `mari_kit.sync.plan_sync` and `stream_sync` for side-effect-free planning.
- `mari_kit.sync.apply_sync_plan` and the `SyncPlanTransaction` protocol for the
  generation-guarded application step.
- `mari_kit.platform.InMemoryDocumentStore` for canonical, scope-isolated,
  compare-and-swap revision persistence.
- `mari_kit` types `KnowledgeDocument`, `DocumentACL`, `Principal`, `PollPage`,
  `Tombstone`, `SyncMode`, `ScopeRef`.

`run()` performs seven cycles (nine planned/applied pages):

1. **Paginated full snapshot** (`stream_sync`, page size 2): three pages; only
   the terminal page is authoritative. Intermediate pages delete nothing and
   hold the cursor; the terminal page advances it.
2. **Incremental poll** with an edit, an addition, a new ACL revision, and an
   explicit provider tombstone; unchanged documents are reported as `unchanged`.
3. **Interrupted full repair snapshot**: the provider dropped `policy/access`,
   but the snapshot is incomplete, so absence is not treated as deletion.
4. **Incomplete-state mode lock**: resuming that state as incremental raises
   `incomplete full sync cannot resume as incremental`.
5. **Completed full snapshot**: the terminal page reconciles absence and deletes
   `policy/access` with reason `absent_from_complete_snapshot`.
6. **Generation conflict**: two plans are computed from generation 6. The first
   commits and advances to 7; the competing plan is rejected by
   `apply_sync_plan` with `sync generation mismatch: expected 6, found 7`, and
   no write occurs.
7. **Recovery and idempotent replay**: the next poll applies the rejected
   document; replaying the same page produces zero upserts and zero deletes.

The host transaction stages upserts/deletes and flushes them in `commit`, so the
generation check runs before any mutation. The reference store keeps deleted
revisions in history (immutability); tombstones remove the document from the
live projection and manifest only.

## Commands and results

```text
$ .venv/bin/python -m pytest tests/test_company_brain_sync.py -q
7 passed in 0.07s

$ .venv/bin/ruff format --check examples/company_brains/sync.py tests/test_company_brain_sync.py
2 files already formatted

$ .venv/bin/ruff check examples/company_brains/sync.py tests/test_company_brain_sync.py
All checks passed!
```

`run()` output (selected, via `python -m examples.company_brains.sync`):

```text
cycles: 9
snapshot_upserts: 5 documents
snapshot_deletes: []
snapshot_cursor_held_until_complete: true
incremental_upserts: [policy/benefits, policy/refunds, policy/security]
incremental_deletes: [policy/payroll]
payroll_tombstone: {removed_from_active: true, removed_from_manifest: true, revision_history_length: 1}
interrupted_cursor_held: true
incremental_resume_rejected: "incomplete full sync cannot resume as incremental"
reconcile_deletes: [policy/access]
reconcile_reasons: [absent_from_complete_snapshot]
generation_conflict: {base_generation: 6, competing_error: "sync generation mismatch: expected 6, found 7"}
recovery_upserts: [policy/travel]
replay_upserts: []; replay_deletes: []
active_external_ids: [policy/benefits, policy/onboarding, policy/refunds, policy/security, policy/travel]
final_generation: 9
generations: [1..9]; generations_strictly_increasing: true
```

The full test suite for the touched areas also passes: `pytest
tests/test_company_brain_sync.py tests/test_sync.py
tests/test_composition_primitives.py -q` -> `31 passed`.

## Library bugs

**No core bug was found in the exercised planner/application paths.** The
generation contract, pagination, tombstone, and incomplete-snapshot safeguards
all behaved as documented. No test was weakened or xfailed.

The closest issue is a persistence/API gap rather than a planner bug (see
below). It is recorded by a passing test that pins the observable seam, not by a
failing/xfailed test, because the library explicitly leaves persistence to the
host and the provider-revision contract makes the behavior defensible.

## API gaps

1. **ACL/metadata-only upserts cannot be persisted through the reference
   `DocumentStore`.** `plan_sync` fingerprints provider ACL metadata
   (`document_fingerprint` includes `acl`, `metadata`, `title`, `updated_at`,
   `source_url`), so an ACL-only observation is correctly planned as an upsert
   even when `KnowledgeDocument.revision` is unchanged. But
   `InMemoryDocumentStore.commit` rejects a second commit with the same
   `revision` (`ValueError: document revision already exists`) because it models
   immutable revisions. The library's own examples avoid this by having the
   provider bump its revision (e.g. Google Drive `modifiedTime`), so this is a
   host/provider contract question, not a planner defect. A host that receives a
   genuine ACL-only change has no reference-store path to persist it.
   *Suggested core enhancement (optional):* add a revision-preserving observation
   method, e.g. `DocumentStore.observe_acl(document, *, expected_revision)` (or
   key stored revisions by `(revision, fingerprint)`), so ACL/tag observations
   can be recorded with CAS without fabricating a provider revision.
   `tests/test_company_brain_sync.py::test_acl_only_observation_is_planned_but_immutable_store_rejects_it`
   documents the current behavior.

2. **`DocumentStore` has no delete/tombstone operation.** Sync tombstones can
   only be applied to a host-owned live projection and the sync manifest; the
   revision store necessarily retains history. This is consistent with
   immutable revisions but means the store alone cannot answer "what is current
   in the brain" after a deletion. Host responsibility.

3. **`apply_sync_plan` checks only the generation.** It does not verify source
   identity, that the plan matches the transaction's store/scope, or that the
   transaction is atomic. These remain host responsibilities; the reference
   `SyncPlanTransaction` is a protocol the host implements.

## Host responsibilities vs library

- **Library:** planning (upserts/deletes/unchanged), source binding of state,
  full-vs-incremental mode locking, cursor/checkpoint holding, terminal-only
  absence reconciliation, tombstone authority, generation increment, the
  optimistic generation check, and reference revision CAS/scope isolation.
- **Host (this module):** provider I/O, the transaction boundary (staging and
  flush), live projection, ACL-observation persistence strategy, scheduling, and
  durability/rollback. The generation-conflict test proves the library rejects
  the stale plan *before* the host transaction mutates anything.

## Remaining limitations

- The provider is a deterministic in-memory fake; no live connector, network,
  credentials, or scheduler is used.
- The host transaction is not durable and has no rollback: `commit` flushes
  buffered writes sequentially. A failure mid-flush could leave a partial
  projection; a production adapter must supply real atomicity.
- ACL-only changes are exercised through a revision bump (as providers do). The
  same-revision ACL seam is pinned by test but not persisted.
- Authorization is out of scope; `DocumentACL` is only recorded, never enforced.
- Validation is scenario-based, not a fuzzed conformance sweep; the library's own
  `assert_document_store_conforms` covers store semantics separately.
