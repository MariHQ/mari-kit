> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Wave 2 durability builder report

Owner: durability builder. Scope: `examples/company_brains/durable/store.py` and
`tests/test_brain2_store.py`, plus this report. No other files were modified, and
no git, network, install, credential, or subagent actions were taken.

## Files delivered

| File | Role |
| --- | --- |
| `examples/company_brains/durable/store.py` | `SQLiteBrainStore`, host-owned durable persistence |
| `tests/test_brain2_store.py` | 10 direct smoke tests, including real `os._exit` crash tests |
| `artifacts/company-brains-wave2/durability_builder.md` | this report |

`store.py` uses only the standard library plus public Mari values
(`KnowledgeDocument`, `DocumentACL`, `Principal`, `ScopeRef`, `SyncMode`,
`Tombstone`), `mari_kit.json.to_json_value`, and `mari_kit.sync`
(`SyncPlan`, `SyncState`, `ManifestEntry`, `document_fingerprint`). It does not
depend on any sibling wave-2 module.

## What was implemented

- `SQLiteBrainStore(path)`, `close()`, `__enter__`/`__exit__`. `path` may be a
  DB file, an existing directory (a `brain.sqlite3` file is created inside it),
  or `:memory:`.
- One connection per instance, `isolation_level=None` autocommit, bounded
  `busy_timeout = 5000 ms`, `synchronous = FULL`, WAL for file databases.
  Reads therefore observe freshly committed rows from other processes.
- Schema keyed by `(tenant, space)` for `documents`, `projections`,
  `sync_states`, `groups`, and `cache`, plus an append-only `document_history`
  table (keyed by document/revision/fingerprint) that keeps past observations
  separate from the live row.
- `state`, `documents`, `get_document`, `projection`, `set_groups`, `groups`,
  `access_snapshot`, `save_cache`, `load_cache`.
- `apply_plan(scope, plan, *, failpoint=None)` runs one `BEGIN IMMEDIATE`
  transaction: generation check inside the transaction, then live documents,
  the failpoint `after_documents`, the lexical projection, `after_projection`,
  source sync state/generation, `before_commit`, `COMMIT`, `after_commit`.
  Foreign-source upserts/tombstones are rejected before any write. Any
  exception rolls the transaction back explicitly. Same-revision ACL/metadata
  upserts overwrite the live document while history is only appended.
- Serialization uses `mari_kit.json.to_json_value`, preserving ACL principals,
  metadata, times, and every `SyncState` field (`manifest`, `full_seen`,
  `active_mode`, `cursor`, `checkpoint`, `configuration_fingerprint`,
  `generation`). Decoding reconstructs the dataclasses, so values compare equal
  to the originals (Mari metadata remains frozen: sequences are tuples).

## Commands and results

All run from `/Users/henneberger/mari-kit` with the project virtualenv.

| Command | Result |
| --- | --- |
| `.venv/bin/ruff check examples/company_brains/durable/store.py tests/test_brain2_store.py` | `All checks passed!` |
| `.venv/bin/python -m pytest tests/test_brain2_store.py -q` | `10 passed` |
| `.venv/bin/python -m pytest tests/test_brain2_store_review.py -q` | `18 passed` (durability reviewer's audit) |
| `.venv/bin/python -m pytest tests/test_brain2_crash.py -q` | `7 passed in ~36s` (crash tester's real process-death suite, includes competing writers) |
| `.venv/bin/python -c "from examples.company_brains.durable.engine import CompanyBrain"` | import OK (engine drives a store Protocol, not the concrete class) |

`tests/test_brain2_store.py` covers: persistence of documents/projection/state/
cache/groups across reopen; tenant, space, and source isolation; dual rejection
of foreign sources and stale generations without writes; same-revision ACL
observation updating the live document; consistent `access_snapshot`; tombstone
removal; and real `os._exit` kills at `after_documents`, `after_projection`,
`before_commit` (all-or-nothing) and `after_commit` (durable).

## Defects found vs decided host responsibilities

No defect was found in `store.py`; all three independent test suites pass.
The following are recorded as boundaries, not bugs.

1. **Metadata immutability is a host contract.** `KnowledgeDocument` freezes
   JSON metadata (`freeze_json_mapping`): nested sequences round-trip as tuples
   behind `MappingProxyType`, never as lists. A durable store must not try to
   "restore" lists; doing so would break `loaded == original`. During review the
   durability reviewer's first revision compared against a list literal and
   failed; the reviewer corrected it to compare via
   `to_json_value(loaded.metadata)`, after which it passes. Nothing to fix here.
2. **Atomicity is intentionally host-owned.** Mari supplies
   `apply_sync_plan`/`SyncPlanTransaction` as a protocol but no persistence, so
   the store implements the transaction directly. Implementing the protocol
   could reuse `apply_sync_plan`, but that helper still requires the host to own
   `BEGIN IMMEDIATE` and the generation check, so it would add indirection only.
3. **Authorization stays in `engine.py`.** The store persists ACLs and
   memberships faithfully; it does not decide visibility. `access_snapshot`
   returns raw live documents plus the user's groups. This matches the
   permissions builder's ownership.
4. **Directory-path convenience.** Tests pass `str(tmp_path)`, i.e. a directory,
   so the constructor appends `brain.sqlite3`. A non-existent path is treated as
   a file, not a directory. The filename is a convention, not a contract.

### Exact recommended fixes

- None required for `store.py` to satisfy the shared contract.
- Coordinator: treat the database filename convention as `brain.sqlite3` when
  a directory is given; if a different name is desired, pass an explicit file
  path instead of changing `store.py`.
- Reviewer test: keep comparing frozen metadata through `to_json_value` (the
  corrected form); comparing raw `dict(metadata)` to list literals is
  unsatisfiable because Mari freezes sequences.

## Limitations

- WAL requires a local filesystem; do not point the store at a network share.
- `:memory:` databases are process-local and do not survive `close()`.
- Schema is `CREATE TABLE IF NOT EXISTS` only; there is no migration/version
  mechanism. Changing the serialized document/state shape needs a migration.
- `document_history` is append-only and never pruned; retention is a host policy.
- Cache rows have no TTL; staleness/revocation correctness is enforced by the
  engine rechecking current source content, not by the store.
- Groups and cached payloads are stored as plain JSON; do not cache secrets
  unless the host provides encryption at rest.
- A writer holding the lock longer than the 5 s busy timeout raises
  `sqlite3.OperationalError` from `BEGIN IMMEDIATE`; it is not translated to a
  domain error. Generation conflicts do raise `ValueError` with
  `"generation mismatch"`.
- `apply_plan` trusts that `plan.state.generation == expected_generation + 1`
  (the pure planner guarantees this); it only verifies `expected_generation`
  against the stored generation.
