# Company brains — wave 7

Three parallel OpenCode `deepseek/deepseek-flash` agents audited store lifecycle,
the host API, and recovery. Session IDs are in `sessions.json`; raw logs are
ignored. The coordinator reproduced the rollback failure independently and
reviewed/integrated the changes.

## Fixed

- Empty database paths now raise `ValueError`, preventing SQLite from silently
  opening a temporary database whose contents disappear on close.
- A secondary rollback no longer masks SQLite's original transaction failure.
  Membership updates, read snapshots, and sync writes share the error-preserving
  rollback helper.
- Operations on a closed store raise SQLite's `ProgrammingError`; repeated
  close remains safe.
- Custom integer/string/tuple access tokens retain their values in view-cache
  keys instead of collapsing to zero epochs and replaying stale answers.
  Epoch keys and opaque keys are distinct. Absent, unhashable, or malformed
  epoch tokens disable view retention. Hosts must supply stable, immutable
  tokens and consistent token/snapshot reads.

The durable README now describes partial-sync restart, after-commit failures,
and the requirement to construct fresh stores/brains after database restoration.

## Validation

- Full suite: **1,233 passed** (1,193 baseline + 40 wave-7 cases).
- Recovery cases cover interrupted full/incremental pages, restart from durable
  checkpoints, process death before/after commit, scope/source/user isolation,
  and fresh versus warm answer-cache invalidation.
- The coordinator's trigger regression failed on the baseline and passes with
  the fix. Token tests verify both source edits and membership revocations.
- Ruff lint/format and Pyright pass. Wheel/sdist build, installed-wheel durable
  smoke test, existing examples, company-brain scenarios, durable lifecycle,
  algorithm inventory, Sphinx, and browser sidebar checks pass.
- `admission.json` confirms the earlier oversized-view fix still preserves the
  useful warm view without an extra snapshot reload.

Curated fixture results are adjacent JSON files. Agent reports retain their
handoff observations; this file describes the integrated result.

## Limits

No new live-model quality measurement was run. Recovery coverage exercises
process death, not hardware power loss or online database replacement. Hosts
still own authentication and restore operations; restored memberships must be
reconciled before serving data. Arbitrary raw SQL bypasses access counters.
