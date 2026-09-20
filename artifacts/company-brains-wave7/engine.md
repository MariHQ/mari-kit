> Agent handoff report. Counts and implementation details reflect the agent
> handoff; see [integrated results](README.md) for the final wave.

# Wave 7 — durable engine (`examples/company_brains/durable/engine.py`)

Scope: API edge cases, cache invalidation and mutation during callbacks,
scope/user binding and retries. One concrete correctness bug was demonstrated
and fixed; the callback/retry and scope-binding paths were exercised but held.

## Finding (fixed): opaque access token collapses the view-cache key

`CompanyBrain._view_key` built the retained-view key from
`int(getattr(token, "doc_epoch", 0))` and
`int(getattr(token, "membership_epoch", 0))`. The documented `AccessToken`
exposes those counters, but the optional token API (`access_token` /
`access_token_snapshot`) accepts any host token. A store whose token is an
opaque monotonic integer, string, or tuple therefore keyed **every** token as
`(scope, user, 0, 0)`.

Consequence: after a durable edit the stale memoized view was found under the
collapsed key, its stale authorized digest matched the stale persisted answer
record, and `answer()` replayed the pre-edit prose with `cache_hit=True`.

Reproduction (pre-fix): a store whose `access_token` returns a monotonic int and
whose `apply_plan` bumps it; warm `"30 days"`, edit body to `"99 days"` →
`answer()` returned `"30 days"`, `cache_hit=True`. This is a real authorization
correctness failure: source invalidation is defeated by a conforming host token.

### Minimal fix

`_view_key` now binds the token's **value** when it is not an epoch pair, and
declines to retain a view for `None`/unhashable tokens (falling back to the
legacy uncached read) instead of colliding:

- epoch-bearing token → `(doc_epoch, membership_epoch)` (unchanged fast path);
- other hashable token (int/str/tuple/…) → the token value itself;
- `None` or unhashable token → no view is retained.

`_lookup_view` / `_store_view` treat a `None` key as a miss / no-op. New alias
`_ViewKey = tuple[tuple[str, str], str, object]` replaces the old 4-tuple
annotations. Epoch-token behaviour, key prefix `[0] == scope.key` and
`[1] == user_id`, eviction, and byte accounting are unchanged.

## Exact tests — `tests/test_brain7_engine.py` (4 new)

- `test_opaque_token_change_invalidates_the_memoized_view`
  — monotonic-int-token store; warm is grounded on `OLD_BODY`, repeat is a hit,
  edit to `NEW_BODY` yields `cache_hit is False`, `NEW_BODY` present and
  `OLD_BODY` absent.
- `test_unhashable_token_is_not_retained_but_stays_correct`
  — list-token store; post-edit answer is fresh and `cache_stats().views == 0`.
- `test_epoch_token_store_still_retains_and_invalidates`
  — positive control on the real `SQLiteBrainStore`: warm view retained
  (`views == 1`), post-edit answer fresh, view still retained.
- `test_view_key_binds_distinct_opaque_tokens`
  — `_view_key` distinguishes `1` vs `2`, returns `None` for `None`/`[]`, and
  still returns `(scope, "alice", (3, 4))` for an `AccessToken`.

## Verified scenarios (no change needed)

- Retry exhaustion while a callback mutates on every call: abstention returned,
  never cached, recovery works (`tests/test_brain2_integration.py:43`).
- Mutation during callbacks (body/title/ACL/delete/add, cross-connection):
  reruns and re-serves against the current fingerprint; no stale prose
  (`test_brain3_cache.py`, `test_brain5_cache.py`, `test_brain4_adversarial.py`).
- Scope switch during generation: retries against the new scope, attributes the
  persisted record to the live scope (`test_brain4_integration.py:102`,
  `test_brain4_adversarial.py:810`).
- User/tenant binding: answer key is question+user and store-scoped; view key
  carries scope+user+token (`test_brain2_access_review.py`).
- Pressured admission and byte budgets: unchanged and still passing
  (`test_brain6_admission.py`, `test_brain6_pressure.py`).

## Verification

```
.venv/bin/python -m pytest -q                 # 1228 passed (1224 peer baseline + 4)
.venv/bin/python -m ruff check <files>        # All checks passed
.venv/bin/python -m ruff format --check <files>  # already formatted
```

## Residual gaps (not fixed — no demonstrated answer-correctness impact)

- `search(limit=<non-int>)`: `float`/`str`/`None` reach the index and raise a
  low-level `TypeError`; `True`/`False` are silently treated as `1`/`0`.
- `answer(question=<non-str>)`: raises `AttributeError` on `.strip()`.
- A custom `BrainStore` returning two distinct documents with the same
  `document_id` makes `parse_answer` raise `ValueError` from `document_lookup`
  out of `answer`; the SQLite store's primary key makes this unreachable there.
- View cache is keyed by scope/user/token only; replacing `_store` on a live
  brain (private, undocumented) is not covered.

Files touched: `examples/company_brains/durable/engine.py`,
`tests/test_brain7_engine.py`. `store.py` and `cache_records.py` untouched.
