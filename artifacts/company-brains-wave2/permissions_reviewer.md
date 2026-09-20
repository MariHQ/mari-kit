> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Permissions / persistent access-cache review (wave 2)

Owner: permissions reviewer. Reviewed the durable store and permission engine without
editing them, and added an independent access/cache test suite.

## Owned files

- `tests/test_brain2_access_review.py` — 16 compact behavioral tests (new).
- `artifacts/company-brains-wave2/permissions_reviewer.md` — this report.

Reviewed, not edited:

- `examples/company_brains/durable/store.py` (`SQLiteBrainStore`)
- `examples/company_brains/durable/engine.py` (`CompanyBrain`)
- Public surfaces relied on: `mari_kit` `ScopeRef`/`DocumentACL`/`Principal`/`KnowledgeDocument`,
  `mari_kit.sync.{plan_sync, SyncState}`, `mari_kit.knowledge.parse_answer`,
  `mari_kit.retrieval.RevisionBM25Index`.

## Focus areas and coverage

| Required probe | Test |
| --- | --- |
| Cache key cross-tenant / cross-user isolation | `test_store_cache_is_isolated_by_scope`, `test_engine_cache_does_not_leak_across_tenants`, `test_cached_restricted_answer_is_not_served_to_another_user` |
| Stale observations on a long-lived app after another connection changes state | `test_long_lived_brain_observes_another_connections_edit`, `test_long_lived_brain_drops_a_deleted_document` |
| Cache rehydration after restart | `test_cached_answer_rehydrates_after_restart` |
| Malicious callback citing an unauthorized document | `test_hostile_generate_cannot_cite_a_hidden_document`, `test_hostile_generate_cannot_smuggle_a_cross_tenant_document` |
| Trusted tenant/user vs group grant | `test_tenant_visible_policy_and_trusted_identity_grants`, `test_group_grant_is_read_from_store_on_every_request`, `test_group_grant_is_confined_to_its_tenant`, `test_principal_kind_is_not_interchangeable_with_identity` |
| Revoke / same-revision observation change | `test_revoked_group_stops_a_cached_restricted_answer`, `test_same_revision_acl_revoke_invalidates_a_cached_answer` |
| Durable read consistency | `test_state_documents_and_projection_round_trip_after_reopen`, `test_access_snapshot_returns_documents_and_memberships` |

## Commands and results

```
.venv/bin/ruff check tests/test_brain2_access_review.py
# All checks passed!

.venv/bin/python -m pytest tests/test_brain2_access_review.py -q
# 16 passed in 2.31s
```

Environment: Python 3.13.3, ruff 0.16.5. No full-suite run (per contract).

Two additional adversarial probes were run from throwaway scripts in the pre-approved
temp directory to confirm the findings below; they are not part of the committed suite.

## Defects

### D1 (medium) — exhausted-generation abstention is cached and can poison the answer cache

`engine.py:203-216` retries generation up to `_MAX_ATTEMPTS` (3) when the authorized
fingerprint changes between the snapshot and the post-callback re-read. If all attempts
race, the final line returns the abstention with `malformed=False`:

```python
216:        return self._abstention(question, user_id), False
```

`answer()` only skips `save_cache` when `malformed` is true (`engine.py:178-181`), so
this contention abstention is written to the durable cache with the *current*
fingerprint. Once writers go quiet, the fingerprint matches and every subsequent
request for that `(user, question)` is served `cache_hit=True` with
"insufficient evidence" even though the sources are stable and answerable.

Reproduction (temp probe): a `generate` callback that commits an unrelated upsert on a
second connection each call produced

```
attempts 3 disposition insufficient_evidence cache_hit False
second disposition insufficient_evidence cache_hit True answer No authorized evidence ...
```

The correct stable call should have returned the grounded extractive answer. This is a
correctness/availability bug, not a confidentiality bug: no hidden evidence is served,
but a transient write burst permanently suppresses a valid answer until the authorized
set fingerprint changes again.

Exact fix (one line, engine owner):

```python
# examples/company_brains/durable/engine.py:216
return self._abstention(question, user_id), True   # was: ..., False
```

Returning `True` marks the exhausted-attempt abstention as uncached, matching the
existing malformed-output policy at `engine.py:210`; the next request retries
generation and can ground once the store is stable. Optionally add a distinct
"retryable" flag to avoid conflating "model output was malformed" with "content kept
changing", but the boolean fix is sufficient and behavior-preserving for the contract.

### D2 (low, contract edge) — hidden prose can ride in the `answer` field while citing a visible document

`parse_answer` validates *evidence* (document id, revision, exact quote) but not
entailment of the answer text. A hostile `generate` can therefore return an answer
string copied from a restricted/off-tenant document while citing a visible document
whose quote is present in its own body. With one public doc and one hidden doc, a
callback answering with the hidden body was served as `grounded`:

```
disposition grounded cache_hit False
answer The failover region is us-west-2-warm.
hidden leaked: True
```

The engine meets the letter of the contract ("do not allow a callback to cite hidden
sources") and the default generator is extractive-only, so this is not an engine defect
under the current wording. It is a residual risk whenever a host supplies an untrusted
or externally-influenced model callback.

Recommended handling (report-level, host-policy choice):

- Document in the engine docstring that `generate` output prose is trusted, not
  entailed; citations are the enforced boundary.
- For untrusted callbacks, hosts should constrain the answer (for example require the
  answer to be a substring of a cited authorized quote, or drop the answer to the
  extractive fallback when the answer is not derived from authorized text).
- Do not weaken the citation check to compensate.

## Conforming behavior verified (no defect found)

- Cache key `answer:<sha256(question,user_id)>` plus the `(tenant, space, cache_key)`
  primary key gives both cross-user and cross-tenant isolation; a restore-on-same-file
  keeps the separation.
- `CompanyBrain` reads one `access_snapshot` per request instead of constructor state:
  group grants/revocations take effect without rebuilding the brain.
- `_serve_cached` re-derives the current authorized fingerprint and re-checks every
  dependency revision/content digest and every evidence quote before serving, so an
  edit, delete, same-revision ACL revoke, or group change invalidates the cache.
- A long-lived engine on connection A observes a revision written by connection B and
  re-grounds; deletion yields `insufficient_evidence`.
- Cached grounded answers rehydrate after close/reopen on the same database file.
- Hostile citations of a hidden or cross-tenant `document_id` raise
  `MalformedModelOutput`, producing an uncached abstention with no hidden id in
  `evidence`.
- Host policy is exact: `public`/`connector_scope` tenant-visible; `restricted`
  requires `kind=user` matching the caller or `kind=team` matching a current store
  group. Principal kinds are not interchangeable, and a group grant in another tenant
  scope does not grant in this scope.
- Durable round trip preserves ACL principals, metadata, `updated_at`, content digest,
  generation/manifest, and projection; `access_snapshot` returns live documents and
  memberships from one read transaction.
- `apply_plan` checks the generation inside `BEGIN IMMEDIATE` and rejects foreign
  sources before writes; cache/group writes are parameterized and atomic.

## Host responsibilities (explicitly outside engine/store)

- Authentication and the trusted tenant/user identity are supplied by the caller.
- Answer prose trust/entailment for external callbacks (see D2).
- Thread safety: one SQLite connection per `SQLiteBrainStore`; do not share an instance
  across threads.
- Cache size/eviction is unbounded and not implemented; hosts needing bounds must add
  their own maintenance.
- `generate` exceptions other than `MalformedModelOutput` propagate to the caller;
  hosts should wrap untrusted callbacks.

## Limitations

- Focused review only: I did not run the full suite or other owners' test files, and did
  not exercise crash/failpoint durability (durability owner) or the scale path.
- D1/D2 were confirmed with temporary probe scripts, not committed regression tests; my
  suite intentionally validates the conforming contract so it stays green for the
  coordinator. The exact one-line D1 fix above should then be covered by a regression
  test that forces three racing writes.
- The two defects target `examples/company_brains/durable/{engine,store}.py`, which I was
  instructed not to edit; the coordinator or owner should apply the fix.
