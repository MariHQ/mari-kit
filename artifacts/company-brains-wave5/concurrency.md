> Agent handoff report. See [integrated results](README.md) for final validation and publication handling.

> Agent handoff report. Coordinator owns commit/push; this report is evidence for the wave-5 durable concurrency slice.

# Wave 5: cross-process concurrency for the durable company brain

Owner: concurrency test agent. Owned files:

- `tests/test_brain5_concurrency.py` (new, 4 tests)
- `artifacts/company-brains-wave5/concurrency.md` (this report)

No source file, dependency, credential, network resource, other agent's file,
or git state was modified. `store.py` and `engine.py` were read only (and were
observed to change during the run). Nothing was staged, committed, or pushed.

## Scope

Every earlier durable test exercised one interpreter: one `SQLiteBrainStore`
connection, or several connections inside one process. Wave 5 tests the contract
that actually matters for a multi-process deployment: two operating-system
processes, each with its own independent SQLite connection, writing and reading
the same database file. The tests deliberately make **no** of these assumptions:

- **No shared-connection thread safety.** No `SQLiteBrainStore`, `sqlite3`
  connection, cursor, or transaction crosses a process boundary or is used from
  two threads. Each spawned child constructs its own `SQLiteBrainStore` from the
  database path. The parent keeps its own connection as the reader.
- **No retraction of completed reads.** A read that completed before a change is
  never retroactively invalidated. The warmed-answer test holds the original
  result object and asserts it still contains the old prose after a revocation;
  only *subsequent* reads are required to observe the live state.
- **No timing assumptions.** Coordination is by `Barrier`, `Event`, and `Queue`
  only. There are no `time.sleep` calls and no polling loops; every wait has a
  bounded timeout and every child is joined/terminated/killed in a `finally`.

## What was built

`tests/test_brain5_concurrency.py` contains four focused tests using only the
public host surface: `apply_plan`, `set_groups`, `state`, `documents`,
`projection`, `get_document`, `access_token`, and the engine's
`search`/`answer`. The writer processes are module-level functions so they are
picklable and importable under the macOS `spawn` start method.

1. **`test_competing_writers_from_same_generation_commit_exactly_one`** —
   two processes each read the committed generation and plan a distinct
   incremental page, then meet at a `Barrier`, guaranteeing both planned from the
   same `expected_generation`. Writer `0` takes `BEGIN IMMEDIATE`, signals from
   the `after_documents` failpoint, waits for writer `1` to signal that it is
   about to write, and commits. Writer `1` then blocks on the write lock, reads
   the advanced generation, and raises `ValueError: sync generation mismatch`.
   The test asserts exactly one `committed` and one `mismatch`, then verifies
   through a *fresh* connection that the winner's plan is the only durable
   outcome: `state == winning_plan.state`, documents equal the replay of the
   baseline plus the winning plan, `projection` matches the documents exactly,
   the document epoch advanced by exactly one (the loser wrote nothing, not even
   an epoch), the loser's document is absent, and the winner's is present.
   This is the `no partial state` assertion: no half-applied projection, no
   state-only generation advance, no stray epoch.

2. **`test_warmed_reader_observes_cross_process_changes_after_ack`** — the
   parent holds a warmed `CompanyBrain` (both the authorized-view cache and the
   durable answer cache populated) on its own connection while a persistent
   writer process applies four changes on its own connection. After each change
   the writer acknowledges over a `Queue`, and only then does the reader issue a
   new request:
   - **same-revision ACL** (`restricted` moves from `support` to `finance`,
     revision stays `r1`): `doc_epoch` advances by one, search returns nothing,
     and the previously cached grounded answer is not served
     (`cache_hit is False`, no `30 days` in the prose);
   - **membership grant** (`alice` gains `finance`): `membership_epoch`
     advances, no document row changed, and the reader re-authorizes and answers
     grounded again;
   - **same-revision title-only change**: the warmed BM25 index sees the new
     title (`search("legacy")` returns it), proving the view was rebuilt from
     the new document payload, not merely invalidated;
   - **deletion**: the document is gone from the reader's next search and
     answer.
   After the revocation, the test re-asserts that the earlier completed
   `warm` answer still contains `30 days`, documenting the no-retraction rule.

3. **`test_source_progress_survives_restart_and_resumes`** — an authoritative
   full snapshot is split across two pages. A first spawned process applies the
   incomplete page (persisting `active_mode=FULL`, `checkpoint="page:2"`,
   `full_seen`, generation 1) and exits. A second, independent process starts
   over a fresh connection and applies the terminal page; the test asserts it
   resumed from the persisted mode/checkpoint, reconciled the snapshot
   (`active_mode is None`, `full_seen == frozenset()`, `cursor="full:done"`,
   `checkpoint is None`), merged the documents, and kept `projection` exactly
   consistent with them. This is the source-progress/restart case.

4. **`test_rolled_back_plan_is_invisible_and_the_retry_is_observed`** — the
   parent warms a reader, then a child applies an edit with a `before_commit`
   failpoint that raises and forces a rollback, and reports back. The parent
   verifies on its live connection that **nothing** changed: the sync state, the
   document map, the projection, and the access token/epochs are byte-for-byte
   the pre-transaction snapshot, and the warm read is still a cache hit (a
   rolled-back write must not cause a phantom invalidation). The parent then
   releases the child, which re-applies the same plan and commits; the parent
   verifies the document changed and that the reader misses its cache and
   observes `45 days`.

## Results

No source defect was found. The store's optimistic generation check,
`BEGIN IMMEDIATE` serialization, single-transaction epoch bumps, and WAL
visibility to an independent reader connection all behaved correctly under real
multi-process contention; the engine's token-keyed view cache correctly
invalidated on cross-process ACL, membership, title, and delete changes, and
correctly stayed valid across a rolled-back write.

```text
.venv/bin/ruff check tests/test_brain5_concurrency.py           # All checks passed
.venv/bin/ruff format --check tests/test_brain5_concurrency.py  # already formatted
.venv/bin/python -m pytest tests/test_brain5_concurrency.py -q  # 4 passed
.venv/bin/python -m pytest -q                                   # 1102 passed
```

The concurrency tests were run five consecutive times (plus once inside the full
suite) with identical results and no flakes; the single-file run completes in
roughly 1.6 s because every wait is event-driven.

Observed suite counts at run time: **1098** tests collected before this file was
added and **1102** with it, all passing. The coordinator stated a baseline of
1079; the extra collected tests are other in-flight wave-5 files, which this
agent did not read, modify, or count as its own.

Hashes at final validation:

```text
store.py                        7175b31c72d8c4065c7e4ae310a82b3e230786b6853e26967aaa7371a769dd1d
engine.py                       b681237f8bb9244a4965d6fedbb1832aa870d9987244102de5d6fabb7b59db89
tests/test_brain5_concurrency.py eb2c9d4e120cdb5074a93f3e9e7e4569becf0b5cc946092a46897ba0265dd3f7
```

## Reproduce

```bash
.venv/bin/python -m pytest tests/test_brain5_concurrency.py -q
.venv/bin/ruff check tests/test_brain5_concurrency.py
.venv/bin/ruff format --check tests/test_brain5_concurrency.py
```

## Limits

- The tests target the durable single-file SQLite example, not a distributed
  service. They show that independent processes see committed state promptly;
  they do not model clock skew, network partitions, or a cache shared across
  hosts.
- The competing-writer test orders the race deliberately (writer `0` holds the
  write lock while writer `1` attempts), so it pins the "exactly one commits"
  invariant under a realistic lock interleaving rather than relying on scheduler
  luck; a true simultaneous attempt still resolves through the same
  `BEGIN IMMEDIATE`/generation-mismatch path, and the crash-era
  `test_brain2_crash.py::test_competing_writers_from_one_generation_commit_exactly_one`
  covers that shape independently.
- Hardware power loss, backup/restore, and multi-writer service deployment
  remain outside this example.
