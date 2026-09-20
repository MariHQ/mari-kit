# Synchronization planner audit

Adversarial audit of `src/mari_kit/sync/planning.py` (and the host-facing
`apply_sync_plan` contract it feeds) from the perspective of shipping a
continuously synchronized company brain.

## Scope and deliverables

| Path | Status |
| --- | --- |
| `src/mari_kit/sync/planning.py` | Audited; **not modified** (no proven defect). |
| `tests/test_company_brain_sync_audit.py` | Added: 24 adversarial tests. |
| `artifacts/company-brains/sync_audit.md` | This report. |

Only the two paths above were written. No other files, git state, configuration,
credentials, network, or subagents were used.

## Method

1. Read the planner, the application protocol, the shared types
   (`KnowledgeDocument`, `PollPage`, `Tombstone`, `SyncMode`), the strict JSON
   encoder, the connector contract helper, the docs (`README.md`,
   `docs/connectors.md`, `IMPLEMENTATION.md`), and the shipped tests
   (`tests/test_sync.py`, `tests/test_composition_primitives.py`,
   `tests/test_company_brain_sync.py`).
2. Wrote two throwaway, independent oracle harnesses under the OS temp dir
   (not committed) and fuzzed the planner:
   - a reference reconciliation model (manifest vs. an independently tracked
     live set) over random incremental/full page sequences, and
   - an end-to-end provider oracle asserting that after every completed full
     snapshot the host store exactly equals the provider's live set, including
     random pre-commit "crashes" that re-deliver the same page.
3. Encoded the guarantees called out in the task as executable tests in the new
   audit file. Every test passed; no probe falsified a documented behavior.

The oracle harnesses live in the temp directory and are not part of the
repository; their findings are reproduced by the committed tests.

## Probe results

| Probe | Verdict | Evidence / reasoning |
| --- | --- | --- |
| Crash/retry recovery | Pass | `plan_sync` is pure and deterministic; replaying one page from one state yields byte-identical plans. Resuming an interrupted full snapshot carries `full_seen` forward and never reconciles absence early. Crash fuzz (pre-commit replay) kept store == manifest for 3,000 seeds; provider oracle kept store == provider for 4,000 seeds. |
| Incomplete full snapshots | Pass | Absence reconciliation is gated on `mode is FULL and page.snapshot_complete`. Incomplete pages emit no deletes, hold the durable cursor even when the page tries to advance it, and preserve the manifest/full-seen set. Resuming is mode-locked in both directions. |
| Tombstones | Pass | Explicit tombstones delete immediately in either mode, are removed from both `manifest` and `full_seen`, and carry the provider reason. A document tombstoned then re-upserted in the same full snapshot survives. Absent-deletion tombstones reconstruct the exact encoded `source_id`/`external_id`, so reserved characters (`/`, `:`) cannot collide. |
| Contradictory pages | Pass | Duplicate upsert document IDs, duplicate tombstones, and upsert/tombstone overlap in one page are rejected. A page after a terminal page and an empty page iterable are rejected by `stream_sync`. |
| Fingerprint changes | Pass | `document_fingerprint` covers revision, provider revision, content digest, title, body, updated_at, source_url, ACL visibility, ACL principals, and metadata. A test varies exactly one field at a time from a fully populated baseline and asserts the digest changes. Mapping key order is irrelevant; a `metadata={"unchanged": True}` hint cannot mask a real change (the historical bypass is gone). |
| Source binding | Pass | An unbound state binds on first use; a bound state rejects another source. Foreign upserts and foreign tombstones are rejected. `ManifestEntry` retains `source_id`/`external_id` for absent-deletion reconstruction. |
| Generation safety | Pass | Every plan advances exactly one generation, including no-op pages. Two plans from the same generation share `expected_generation`; after the first commits, `apply_sync_plan` rejects the second *before* any `upsert`/`delete`/`commit` side effect. `stream_sync` chains generations across pages. |
| Configuration binding | Pass | The connector configuration fingerprint binds on first use, rejects drift in either direction (different value, or omitted), and tolerates surrounding whitespace via stripping. |

## Bugs

**No proven defect was found in `planning.py`.** `src/mari_kit/sync/planning.py`
is unchanged. No test was weakened, skipped, or xfailed.

The bugs discoverable by static inspection and by the adversarial probes are
absent: the shipped tests plus the 24 new tests pass, and the independent oracle
fuzzing found no divergence between planned state and the provider's live set.

## Adversarial coverage added

`tests/test_company_brain_sync_audit.py` (24 tests) exercises, independently of
`tests/test_sync.py`:

- deterministic replanning of a page from one state (replay safety),
- interrupted-then-resumed full snapshots, including deletion only of documents
  missing after resume,
- stale-plan rejection with zero transaction side effects,
- incomplete pages never deleting and never advancing the durable cursor,
- mode-locking in both directions,
- terminal-snapshot replay as a no-op,
- explicit tombstones in incomplete incremental pages,
- resurrection after an in-snapshot tombstone,
- encoded external identities in absent-deletion tombstones,
- duplicate/contradictory/foreign page rejection,
- single-field fingerprint sensitivity, metadata bypass, and mapping-order
  stability,
- source and configuration binding on first use and drift rejection,
- one-generation-per-plan and `stream_sync` chaining/termination,
- `apply_sync_plan` ordering (upserts, then deletes, then commit).

## Limitations and observations (not fixed)

These are recorded for the shipping team. None is a proven violation of the
planner's documented contract, so none was "fixed" here.

1. **`Incomplete page` may silently have no recovery position.** The docstring
   says intermediate pages "carry a checkpoint", but `plan_sync` does not
   require `page.next_checkpoint` when `snapshot_complete=False`. If a connector
   returns an incomplete page with no checkpoint and no cursor, the next state
   has no durable position and the retry restarts the scan. Restarting a full
   scan is safe (it re-derives `full_seen`), so this is connector-contract
   hygiene, not data loss. `check_connector_contract` already constrains the
   cursor half of this contract.
2. **`stream_sync` does not require a terminal page at end-of-iterable.** A
   truncated full snapshot ends the generator with `state.active_mode` still
   `FULL` and no absence reconciliation; the incomplete plan carries a warning
   string, but the stream itself does not raise. This is fail-safe (stale
   documents are retained, never deleted). Callers should assert
   `state.active_mode is None` (or a terminal plan) before declaring a snapshot
   complete.
3. **`SyncMode` is compared by identity (`is`) internally.** Passing the string
   form of the `StrEnum` (e.g. `"full"`) instead of `SyncMode.FULL` would take
   the non-full branch, so a single-page full snapshot would silently skip
   absence reconciliation. The typed API and every in-repo caller pass the enum
   value, so this is caller misuse rather than a demonstrated defect. (Not fixed
   to avoid inventing a coercion requirement.)
4. **`SyncState` is not hashable and is not `dataclasses.asdict`/`deepcopy`/
   `pickle`-able.** `manifest` is a `MappingProxyType` over a `dict`, which is
   unhashable and unpicklable. This is a library-wide immutability pattern
   (also used by `KnowledgeBundle`, connector configs, verification models), not
   specific to sync. Hosts that persist `SyncState` (as the README instructs)
   must serialize `dict(state.manifest)` explicitly; the planner itself never
   hashes or deep-copies state.
5. **Whitespace normalization is asymmetric for persisted fields.** `plan_sync`
   strips the incoming `source_id` and `configuration_fingerprint`, but
   `SyncState.__post_init__` does not strip values supplied directly to the
   constructor. A hand-built/deserialized state with a padded `source_id` would
   not match a stripped call argument. States produced by `plan_sync` are always
   normalized, so this cannot arise in the normal flow.
6. **Cross-page contradictions within one snapshot are resolved, not rejected.**
   A later page may tombstone or overwrite a document from an earlier page of
   the same scan; the later observation wins. Rejecting this would break
   legitimate mid-scan edits, so the behavior is intentional.
7. **`apply_sync_plan` checks only the generation.** It does not verify source
   identity, store/scope correspondence, or transaction atomicity — all
   explicitly host responsibilities per the `SyncPlanTransaction` protocol.

## Commands and results

All commands run with `.venv/bin/python` from `/Users/henneberger/mari-kit`.

```text
$ .venv/bin/python -m pytest tests/test_company_brain_sync_audit.py -q
24 passed

$ .venv/bin/python -m pytest tests/test_company_brain_sync_audit.py \
    tests/test_sync.py tests/test_company_brain_sync.py \
    tests/test_composition_primitives.py tests/test_connector_contract.py -q
58 passed

$ .venv/bin/ruff format --check tests/test_company_brain_sync_audit.py \
    src/mari_kit/sync/planning.py
2 files already formatted

$ .venv/bin/ruff check tests/test_company_brain_sync_audit.py \
    src/mari_kit/sync/planning.py
All checks passed!
```

Full-suite run at audit time:

```text
$ .venv/bin/python -m pytest -q --ignore=tests/test_revision_index_updates.py
744 passed
```

Two caveats about the full-suite number:

- `tests/test_revision_index_updates.py` fails at collection with
  `ImportError: cannot import name 'RevisionIndexDelta' from 'mari_kit.retrieval'`.
  That is an unrelated, pre-existing work-in-progress from a concurrent agent,
  outside this audit's ownership, and was excluded rather than touched.
- Concurrent agents are adding files to the same tree, so the passing count
  moves between runs. The focused audit and sync suites were stable at
  `24 passed` and `58 passed` throughout.

`git diff --stat src/mari_kit/sync/planning.py` is empty: the audited file was
not modified.
