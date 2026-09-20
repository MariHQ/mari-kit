# Coordinator regression

A real SQLite trigger using `RAISE(ROLLBACK, 'membership update rejected')`
reproduced a secondary rollback masking the original `IntegrityError` with
`OperationalError: cannot rollback - no transaction is active`.
`tests/test_brain7_rollback.py` failed before the store fix and passes afterward.
It checks unchanged memberships and epochs after failure, a successful subsequent
write on the same connection, and the successful write surviving reopen.

The coordinator also strengthened the engine handoff: custom-token test stores
now derive both document and membership state from the same SQLite snapshot;
integer/string/tuple cases check edits and revocations. Epoch and opaque keys
use distinct tags. Missing, fractional, and negative epoch fields disable view
retention instead of being truncated or defaulted. The final 9 engine cases
include the real SQLite fast path and absent/unhashable tokens.
