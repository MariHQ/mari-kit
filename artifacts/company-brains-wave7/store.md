> Agent handoff report. Counts and implementation details reflect the agent
> handoff; see [integrated results](README.md) for the final wave.

# Wave 7 — durable store lifecycle review

Owner: OpenCode `deepseek/deepseek-flash` (wave-7 store owner).
Scope: `examples/company_brains/durable/store.py` and new
`tests/test_brain7_store.py`. Read-only with respect to `engine.py`,
`cache_records.py`, `README.md`, the coordinator's `test_brain7_rollback.py`,
and other agents' wave-7 files. No git mutations, installs, credentials, or
subagents.

## Verdict

Three reproducible store defects found and fixed. The rest of the reviewed
lifecycle surface (restart, checkpoint durability, access-counter rollback,
generation guarding) behaved correctly and is now pinned by regression tests.

## Bug 1 — a secondary `ROLLBACK` masked SQLite's original failure

`set_groups` (and the two read-snapshot methods) wrapped the transaction in an
`except BaseException: connection.execute("ROLLBACK"); raise`. Some SQLite
failures roll the transaction back themselves (e.g. a `RAISE(ROLLBACK)` trigger,
or `SQLITE_FULL`). The explicit `ROLLBACK` then raised
`OperationalError: cannot rollback - no transaction is active`, replacing the
true cause (the coordinator reproduced this with a real trigger; see
`coordinator.md`).

```
set_groups + BEFORE INSERT trigger RAISE(ROLLBACK, 'membership update rejected')
  before fix -> sqlite3.OperationalError: cannot rollback - no transaction is active
  after fix  -> sqlite3.IntegrityError: membership update rejected
```

`apply_plan` already swallowed the secondary error; `set_groups`,
`access_snapshot`, and `access_token_snapshot` did not.

## Bug 2 — operations after `close()` leaked `AttributeError`

`close()` set `self._connection = None` (with a `# type: ignore`), so any later
call failed with `AttributeError: 'NoneType' object has no attribute 'execute'`
instead of the standard SQLite lifecycle error.

```
store.close(); store.documents(scope)
  before fix -> AttributeError
  after fix  -> sqlite3.ProgrammingError: Cannot operate on a closed database.
```

`close()` remains idempotent, because `sqlite3.Connection.close()` is itself
idempotent.

## Bug 3 — an empty path silently opened a throwaway database

`_resolve_path("")` returned `""`, and `sqlite3.connect("")` opens a private
temporary database whose rows vanish when the connection closes. Writes
appeared to succeed and were lost on `close()`. The store now rejects it.

```
SQLiteBrainStore("")
  before fix -> opens temp DB, data lost on close
  after fix  -> ValueError: database path must not be empty
```

## Fixes (`examples/company_brains/durable/store.py`)

- Added `_rollback(connection)` (line 152) that swallows only a secondary
  `sqlite3.Error`; used by `set_groups` (373), `access_snapshot` (389),
  `access_token_snapshot` (416), and `apply_plan` (475).
- `close()` (302) now just closes the retained connection; later calls surface
  `sqlite3.ProgrammingError`.
- `_resolve_path` (135) rejects `""` before touching the filesystem (144).

## Verified correct (no change; pinned by tests)

- **Restart**: documents, projection, `SyncState`, memberships, cache, and both
  access epochs survive close/reopen; a new plan continues from the durable
  generation and advances the document epoch by exactly one.
- **Checkpoint durability**: an incomplete full snapshot keeps
  `active_mode=full`, `checkpoint`, `full_seen`, and its documents across a
  failed plan and a restart; a no-op intermediate page (no upserts/deletes)
  still persists its checkpoint and generation; the terminal page clears the
  checkpoint and reconciles absence.
- **Transaction failure**: an interrupted plan (failpoint or a failed
  `_bump_scope_epoch`) rolls back documents, projection, state, and the access
  token together, and the connection stays usable.
- **Access counters**: `apply_plan` bumps `doc_epoch` only when documents
  change and `set_groups` bumps `membership_epoch` only on a real change.
- **Path handling**: `:memory:` is private per instance; an existing directory
  holds `brain.sqlite3`; nested parents are created; str and `PathLike` inputs
  address the same file.

## Tests (`tests/test_brain7_store.py`, 14 tests)

Restart: `test_restart_preserves_documents_projection_state_membership_cache_and_epochs`,
`test_reopened_store_resumes_an_incomplete_full_snapshot_from_checkpoint`.
Transactions: `test_set_groups_auto_rollback_preserves_error_membership_and_connection`,
`test_apply_plan_auto_rollback_preserves_error_and_whole_plan`,
`test_access_counter_failure_rolls_back_documents_projection_and_state`.
Closed connection:
`test_closed_store_operations_raise_programming_error_and_close_is_idempotent`,
`test_context_manager_closes_the_connection`.
Path: `test_memory_path_is_private_to_the_instance`,
`test_existing_directory_path_stores_brain_sqlite3_and_survives_restart`,
`test_nested_parent_directories_are_created`,
`test_pathlike_and_string_paths_address_the_same_database`,
`test_empty_path_is_rejected_instead_of_opening_a_temporary_database`.
Checkpoint: `test_incomplete_checkpoint_survives_a_failed_plan_and_a_restart`,
`test_noop_intermediate_page_still_persists_its_checkpoint`.

```bash
.venv/bin/ruff check examples/company_brains/durable/store.py tests/test_brain7_store.py
.venv/bin/ruff format --check examples/company_brains/durable/store.py tests/test_brain7_store.py
.venv/bin/python -m pytest tests/test_brain7_store.py tests/test_brain7_rollback.py -q
.venv/bin/python -m pytest -q          # 1,224 passed
```

## Residual observations (not fixed, no demonstrated defect)

- `file:` URIs are recognized by `_resolve_path` but `sqlite3.connect` is not
  passed `uri=True`; this works on builds compiled with `SQLITE_USE_URI`, yet a
  build without it would treat the URI as a literal filename. No failure was
  reproducible here, so it was left unchanged.
- A `bytes` path raises `TypeError` from `str.startswith`; bytes is outside the
  declared `str | os.PathLike[str]` signature.
- A non-existent directory-like path (with or without a trailing separator) is
  treated as a database file; this matches the documented "accept a directory"
  contract only for existing directories.
- SQLite WAL checkpointing uses the driver default; durability across process
  death is covered by `tests/test_brain2_crash.py`.
