> Agent handoff report. See [integrated results](README.md) for coordinator fixes and final verification.

# Wave 6 — Admission: oversized authorized views must not pollute the cache

## Scope and ownership

This wave owns exactly two source files plus this report:

- `examples/company_brains/durable/engine.py` — the fix.
- `tests/test_brain6_admission.py` — the contract tests.
- `artifacts/company-brains-wave6/admission.md` — this report.

No other engine, store, benchmark, or test file was modified. The other files
present under `examples/company_brains/`, `benchmarks/`, `artifacts/company-brains-wave6/`,
and `tests/` belong to other parallel agents and were left untouched.

## Problem

The authorized-view cache is bounded by count (`view_cache_size`) and by an
approximate retained-byte budget (`view_cache_bytes`). Before this wave, a view
that exceeded the byte budget **on its own** was still inserted at the
most-recently-used end and then the generic LRU walk ran:

```
_store_view:  insert(new); enforce()        # enforce evicts from the oldest end
_after_index_built: enforce()               # lazy index growth does the same
```

Because enforcement always evicted the *oldest* view first, admitting one
oversized authorized corpus evicted every smaller, useful cached view on its
way out before finally discarding the oversized view itself. The cache ended
colder than it started, and the next request for a previously-hot user paid a
full live-snapshot reread and index rebuild. The same happened when a lazily
built BM25 index grew an already-cached view past the budget.

## Fix

`examples/company_brains/durable/engine.py`:

- `_enforce_view_limits(oversized=None)` (engine.py:493) now drops a specific
  `oversized` view first, by identity, when its `estimated_bytes()` alone
  exceeds `view_cache_bytes`, and only then runs the unchanged generic count /
  byte LRU loop.
- `_drop_view_object(view)` (engine.py:524) removes a single view by identity,
  so dropping the candidate never depends on its LRU position.
- `_store_view` passes the just-admitted view as the candidate
  (engine.py:472), so it is discarded before any other view is considered.
- `_after_index_built` passes the grown view as the candidate
  (engine.py:477), so lazy-index growth is handled the same way.

Two properties were deliberately preserved:

1. `_evict_obsolete_views` still runs unconditionally before enforcement
   (engine.py:471). A token change revokes the user's older views even when the
   replacement view is itself too large to cache, so revoked access never
   lingers merely because the new view was discarded.
2. The generic LRU loop is unchanged. When several individually-in-budget views
   together exceed the budget, the oldest view is still evicted first, and the
   count bound is enforced exactly as before.

The oversized view may still serve the request that built it: callers hold
their own reference, and enforcement only affects cache membership.

## Tests

`tests/test_brain6_admission.py` (9 tests):

| Test | Contract |
| --- | --- |
| `test_base_oversized_view_does_not_evict_hot_small_view` | After a bulk user's base-oversized search, the hot small-user view is still the same object, retained bytes stay under budget, and the next small-user search does not reread the live snapshot (only the bulk build did). |
| `test_oversized_view_still_serves_its_current_request` | The oversized search returns its own authorized hits while retaining zero views. |
| `test_lazy_index_oversize_does_not_evict_hot_small_view` | A view admitted on its base size whose lazy BM25 index then exceeds the budget is dropped first; the hot small view survives, its next answer is a cache hit, and no extra snapshot read occurs. |
| `test_obsolete_view_is_revoked_even_when_replacement_is_oversized` | After a token change, the user's old view is gone even though the oversized replacement is discarded, leaving zero views for that user. |
| `test_count_bound_still_evicts_lru_for_in_budget_views` | With `view_cache_size=1` and no byte budget, the newest in-budget view still evicts the LRU view. |
| `test_zero_byte_budget_retains_nothing_but_serves` | `view_cache_bytes=0` serves every request and rereads each time, retaining nothing. |
| `test_oversized_eviction_is_scope_isolated` | An oversized search in one scope leaves another scope's brain and cached view untouched. |
| `test_persisted_record_checksum_still_guards_after_oversized_view` | After an oversized admission, a sealed record is served as a hit, and a tampered/unsealed record is rejected and regenerated. |
| `test_record_size_is_still_independent_of_oversized_corpus` | The persisted v3 record still carries the fixed-width 64-hex digest and stays far smaller than the authorized bulk body. |

The tests measure budgets at runtime from the engine's own
`_retained_size` estimate (via unbounded probe brains), so they do not depend on
hard-coded byte sizes.

## Verification

- Pre-fix, run against the `HEAD` engine: `2 failed, 7 passed`. The two
  failures are exactly the base-oversize and lazy-index-oversize pollution
  tests; the seven preservation tests already passed.
- Post-fix: `9 passed`.
- Full suite: `1140 passed` (baseline was reported as 1102; the extra tests are
  the concurrent wave-6 agents' additions, which also pass).
- `.venv/bin/ruff check` and `ruff format --check` are clean for both owned
  files.

The independent benchmark artifacts `admission-before.json` and
`admission-after.json` (owned by a parallel agent) corroborate the same shape:
the small user's view goes from evicted (0 views, +1 snapshot reload) before the
fix to retained (1 view, 0 reloads) after it.
