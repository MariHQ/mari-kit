> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Durability breaker report (wave 2)

Owner: durability breaker agent. Scope: process-death durability of the
host-owned `SQLiteBrainStore` against `CONTRACT.md`.

Verdict: **all focused durability checks pass; no store defects found.**
Every failpoint crash leaves either the complete previous snapshot or the
complete new snapshot, never a partial one. One test-only hardening addition
(foreign-source rejection) also passes.

## Owned files

| File | Purpose |
| --- | --- |
| `tests/test_brain2_crash.py` | 8 behavioral tests: 4 failpoint deaths, partial full-snapshot resume, fresh-process reopen, rejected foreign-source plan, competing generation writers. |
| `examples/company_brains/durable/crash_worker.py` | Subprocess harness. Installs `failpoint` hooks that call `os._exit(0)` at the named stage; also `seed`, `full-page`, `read`, and `compete` modes. Shared fixtures so the test can build expectations independently. |

No other files were edited. `store.py` was read only, never modified.

## Commands and results

```
# lint + format on owned files
.venv/bin/ruff check tests/test_brain2_crash.py examples/company_brains/durable/crash_worker.py
  -> All checks passed!
.venv/bin/ruff format --check tests/test_brain2_crash.py examples/company_brains/durable/crash_worker.py
  -> 2 files already formatted

# focused durability suite (real store.py present)
.venv/bin/python -m pytest tests/test_brain2_crash.py -v --durations=10
  -> 8 passed in 4.01s
     after_documents        PASSED
     after_projection       PASSED
     before_commit          PASSED
     after_commit           PASSED
     partial full snapshot  PASSED
     fresh-process reopen   PASSED
     foreign-source reject  PASSED
     competing writers      PASSED
```

Pre-integration, before `store.py` existed, the same test file and worker were
run end-to-end against a throwaway contract-faithful SQLite reference store in
`$TMPDIR/opencode/brain2harness` (outside the repo, since creating another
agent's file is forbidden): `7 passed in 31.22s`. This validated the harness
(subprocess death, stage markers, barrier, expected-snapshot reducer) before the
real store landed. The real store then passed all 8 without test changes.

## What is proven

1. **All four failpoint stages are all-or-nothing.** A child process is killed
   with `os._exit(0)` immediately after `after_documents`, `after_projection`,
   `before_commit`, or `after_commit`. After reopening the database in the
   parent process, documents, lexical projection, and `SyncState` are compared
   for exact equality with an expected snapshot computed by Mari Kit's pure
   `plan_sync` reducer:
   - pre-commit stages: byte-for-byte the previous committed snapshot
     (generation unchanged, new `policy/security` absent, tombstoned
     `policy/travel` still present, projection equals live documents);
   - `after_commit`: exactly the new snapshot, durable across process death.
   - Each test asserts the stage marker file exists, so a store that silently
     skipped a failpoint cannot pass the `after_commit` case.
2. **Partial full-snapshot resume.** A 3-page authoritative full snapshot is
   applied; page 2 is killed at `after_projection`; a fresh process then resumes
   page 2 and the terminal page 3. The final state equals replaying all pages
   with the pure planner, and after the crash the store is exactly page 1 (no
   partial page 2 row, no partial projection, `active_mode=full`,
   `full_seen`/`checkpoint` preserved).
3. **Fresh-process reopen.** A committed incremental change is read back in a
   separate process and matched field-by-field (state JSON, document revisions
   and bodies, projection) against the independent reducer. `documents()` order
   is stable across repeated reads.
4. **Competing generation writers.** Two child processes each read the same
   base generation behind a file barrier, then apply distinct incremental plans.
   Exactly one commits (exit 0); the other fails with a `generation mismatch`
   before writing. Final state equals the winner's plan, generation advanced by
   exactly one, and exactly one of the two candidate documents exists — no lost
   and no double update.
5. **Foreign-source rejection writes nothing.** A plan carrying a document from
   another `source_id` is rejected with `ValueError` and leaves documents,
   projection, and state identical to the committed baseline.

## Defects vs. host responsibilities

No defects in `store.py`. The following are correctly *host* (application)
responsibilities under `CONTRACT.md` and are therefore outside the store's
durability guarantee:

- **Identity, authentication, and authorization** (engine/`CompanyBrain`) are
  not exercised here. This report only proves that ACL principals, metadata,
  timestamps, and all sync-state fields round-trip losslessly through SQLite
  (covered indirectly by full-document equality across process death).
- **Mari Kit's immutable revision API** is not mutated by the host; the store
  keeps its own `documents`/`document_history`/`projections` tables, as
  required.

## Recommended fixes

- None required for durability. The store already uses `BEGIN IMMEDIATE`,
  in-transaction generation checks, bounded `busy_timeout`, explicit rollback,
  `synchronous=FULL`, WAL, and `mari_kit.json.to_json_value`.
- Optional hardening (not needed for the contract): add a test asserting a
  replayed terminal plan for an already-committed generation is rejected
  (idempotency by generation), and crash-inject inside `set_groups`/`save_cache`
  if those ever become transactionally coupled to documents.

## Limitations

- Crash injection is at the store's declared Python failpoints, not at
  arbitrary byte offsets or simulated power loss; SQLite's own crash-safety is
  assumed when the process dies between failpoints.
- The competing-writer race uses two processes and a file barrier. It proves
  generation rejection and absence of lost updates, not behavior under heavy
  contention or when a writer holds `BEGIN IMMEDIATE` longer than the 5s busy
  timeout.
- The independent expected snapshot comes from Mari Kit's pure `plan_sync`, so
  it is independent of the SQLite code but not of the Mari Kit planner.
- Single source (`handbook`) and small deterministic fixtures; not a scale or
  multi-source durability study. Cache/groups/`access_snapshot` crash behavior
  is not stress-tested (their use in the crash path is not required by the
  contract).
- The temporary reference store used for pre-integration validation lives
  outside the repository and is not a deliverable.
