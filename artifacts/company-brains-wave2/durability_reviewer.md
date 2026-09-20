> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Durability reviewer report (wave 2)

Owner: durability reviewer. Scope: serialization and transaction design of
`examples/company_brains/durable/store.py`; owned test file
`tests/test_brain2_store_review.py`; owned report `durability_reviewer.md`.

Pinned artifact under review:
`examples/company_brains/durable/store.py` sha256
`416b7396f3df259a5db02a69b74c3035be7c310973897a6845d14678273b47bd`
(444 lines, mtime 2026-09-19T17:25:06). `store.py` was not modified by this
review. Crash/process-death durability (`os._exit` failpoints in
`crash_worker.py`) is the crash tester's domain and is not duplicated here.

## Commands and results

```
.venv/bin/ruff check tests/test_brain2_store_review.py
  -> All checks passed!

.venv/bin/python -m pytest tests/test_brain2_store_review.py -q -p no:cacheprovider
  -> 18 passed in 1.58s
```

No full-suite run (per contract). No git changes, installs, credentials, or
subagents.

## What was audited and observed

### Serialization (`_encode` / `_decode_document` / `_decode_state`)

- `_encode` uses `mari_kit.json.to_json_value`, not `dataclasses.asdict`.
  This is required: `KnowledgeDocument.metadata` and `SyncState.manifest` are
  `MappingProxyType`, which `asdict` deep-copies and fails on. Verified directly.
- ACL principals, visibility, `provider_revision`, `source_url`, `updated_at`,
  and nested metadata (dict/list/bool/None/unicode/float) roundtrip by full
  dataclass equality across close/reopen. Timezone-aware input canonicalizes to
  UTC `Z` and survives.
- `SyncState` roundtrips `source_id`, `configuration_fingerprint`, `cursor`,
  `checkpoint`, `manifest` (every `ManifestEntry`), `full_seen`, `active_mode`
  (`SyncMode` enum), and `generation`; an incomplete-full state preserves
  `active_mode=FULL` and `full_seen`.
- Cache payloads roundtrip; `to_json_value` normalizes `datetime` in cache
  payloads to `...Z`; cache is scope-keyed.

### Transactions (`apply_plan`, `set_groups`, `access_snapshot`)

- One `BEGIN IMMEDIATE` transaction covers documents, projection, and sync
  state/generation. Generation is read from `sync_states` **inside** the
  transaction, so two connections that planned from the same generation cannot
  both commit (verified with two connections: loser raises generation mismatch
  and writes nothing).
- Foreign-source upserts/tombstones are rejected before `BEGIN` and before any
  write; state, documents, and projection are unchanged on rejection.
- Failpoints raise ordinary Python exceptions at `after_documents`,
  `after_projection`, and `before_commit`; all three roll back documents,
  projection, and state, including from an independent connection, and a later
  valid plan applies cleanly. Stage names/order are exactly
  `after_documents`, `after_projection`, `before_commit`, `after_commit`.
- `after_commit` fires after `COMMIT` and outside the rollback `try`; a raise
  there leaves the committed rows intact (host/observer failure cannot undo a
  committed plan).
- Explicit `ROLLBACK` is issued for any `BaseException` on the pre-commit path;
  `set_groups` and `access_snapshot` likewise.
- Independent connections on the same file see freshly committed rows (WAL);
  `access_snapshot` reads documents and memberships inside one `BEGIN` read
  transaction, so the returned pair is mutually consistent.
- Tenant separation holds for byte-identical source/external IDs: documents,
  projection, sync state/generation, groups, and cache are all keyed by
  `(tenant, space, ...)`.
- Same-revision ACL/metadata observations update the live `documents` row (no
  false "duplicate revision" rejection) while `document_history` stays keyed by
  fingerprint, keeping history separate from the current observation.
- Projection tracks edits and tombstones; deleted documents disappear from
  `documents`, `projection`, and `get_document`.

## Defects vs host responsibilities

**No contract-violating defects found** in serialization or transaction design
for the pinned revision. The behaviors the contract makes the store responsible
for were independently reproduced.

### Residual risk / optional hardening (not a contract violation)

1. **Store trusts `plan.state.generation` verbatim.** The store checks
   `plan.expected_generation` against the durable generation, then persists
   `plan.state.generation` without asserting it is `expected_generation + 1`.
   A plan not produced by `plan_sync` (e.g. a hand-built `SyncPlan`) can move a
   source's generation backwards or skip ahead; a probe persisted `generation=99`
   from a crafted plan at expected generation 1. Mari's own reference host
   (`apply_sync_plan` + `examples/company_brains/sync.py`) also stores
   `plan.state` verbatim, so this matches the documented transaction protocol;
   the store is not obligated to defend against it. Minimal hardening inside the
   existing transaction, after the mismatch check and before
   `_write_documents`:

   ```python
   if plan.state.generation != plan.expected_generation + 1:
       raise ValueError("plan generation must advance by exactly one")
   ```

   Do this only if the coordinator wants defense-in-depth; otherwise document it
   as a host/planner invariant. Exact one-line location:
   `apply_plan` after line 327 of the pinned revision.

2. **Truthful host boundaries that the store must not absorb** (confirmed
   working as designed): authorization semantics and cache invalidation remain
   in `engine.py`; the store only durably stores ACLs, memberships, and cache
   bytes. `access_snapshot` does not itself authorize: it returns every
   document in the scope plus the user's groups, and the engine filters.
   Provider/source identity is bound only through `plan.state.source_id`; a
   plan carries no scope, so the host must build plans from the same scope it
   applies them to.

### Minor observations (no fix required)

- `_resolve_path` only treats an **existing** directory as a directory; a
  non-existent directory-like path becomes a DB file. Acceptable for the demo.
- `close()` is idempotent; calling store methods after `close()` raises
  `AttributeError`, which is acceptable.
- `document_history` has no public accessor; contract does not require one.

## Recommended fixes

- None required to meet the Wave 2 contract as written. If the coordinator
  wants the generation-monotonicity hardening, apply the snippet above; it is
  the only store change this review would suggest, and it is optional.

## Limitations

- "Independent connections" are two connections in one process; cross-process
  commit visibility and `os._exit` crash semantics are covered by the crash
  tester, not duplicated here.
- Concurrency checks are sequential (plan A commits, then plan B is rejected);
  they do not stress simultaneous writers or lock timeouts. `busy_timeout` is
  configured (5000 ms) but no latency threshold is asserted, per contract.
- Serialization equality is checked through `KnowledgeDocument`/`SyncState`
  equality (frozen values + frozen mappings); this compares semantic values,
  not raw SQLite bytes.
- Authorization policy correctness is out of scope; this review only verifies
  that durable ACL/membership/group data roundtrips faithfully.
