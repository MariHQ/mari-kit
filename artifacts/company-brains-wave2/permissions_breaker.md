> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Permissions breaker report — wave 2 durable revocation

Owner: `permissions_breaker` (revocation/isolation adversarial tests).
Owned files only:

- `tests/test_brain2_revocation.py` (new; 18 focused tests)
- `artifacts/company-brains-wave2/permissions_breaker.md` (this report)

No engine/store files were edited. No git state, installs, credentials, network,
subagents, or full-suite runs were used.

## 1. Target files verified

The store/engine appeared during this task, so the tests were run against the
real implementation rather than left as pending integration:

- `examples/company_brains/durable/store.py` (`SQLiteBrainStore`)
- `examples/company_brains/durable/engine.py` (`CompanyBrain`)

The tests use only the documented public surface from `CONTRACT.md`
(`state`, `documents`, `get_document`, `apply_plan`, `projection`, `set_groups`,
`groups`, `access_snapshot`, `save_cache`, `load_cache`; `search`, `answer`).
They never reach into private members.

## 2. Commands and results

```
.venv/bin/ruff check tests/test_brain2_revocation.py
# All checks passed!

.venv/bin/python -m py_compile tests/test_brain2_revocation.py
# compile-ok

.venv/bin/python -m pytest tests/test_brain2_revocation.py -q
# 18 passed in 3.76s
```

Only this file was run; the full suite was intentionally not run per contract.

## 3. Attack matrix

Two tenants (`tenant-a`, `tenant-b`) hold byte-identical provider IDs
(`source_id="confluence:acme"`, `external_id="page:refunds"`, identical
`document_id`). Users are addressed by the group(s) currently stored in the
store. Each test also asserts an authorized path keeps working.

| # | Attack / property | Test | Result |
|---|---|---|---|
| 1 | unknown source yields empty `SyncState` | `test_state_is_empty_for_an_unknown_source` | pass |
| 2 | two tenants, duplicate IDs: store/engine/projection/cache never cross | `test_two_tenants_with_duplicate_provider_ids_stay_isolated` | pass |
| 3 | restricted docs hidden from search until group membership | `test_search_hides_restricted_documents_until_group_membership` | pass |
| 4 | cached answer revoked by **same-revision** ACL change | `test_cached_answer_revoked_by_same_revision_acl_change` | pass |
| 5 | cached answer revoked by group removal | `test_group_removal_revokes_a_cached_answer` | pass |
| 6 | cached answer revoked by public→restricted change | `test_public_to_restricted_change_revokes_a_cached_answer` | pass |
| 7 | cached answer revoked by deletion; live reads clean | `test_deletion_revokes_a_cached_answer_and_live_reads` | pass |
| 8 | callback revokes group mid-generation | `test_callback_revoking_the_group_during_generation_is_not_served` | pass |
| 9 | callback edits source mid-generation; old prose never served | `test_callback_editing_the_source_during_generation_never_serves_old_prose` | pass |
| 10 | mixed authorized + hidden citations; hidden never reaches `generate` and never appears | `test_mixed_authorized_and_hidden_citations_never_leak_hidden_text` | pass |
| 11 | uncited hidden citation rejected | `test_uncited_hidden_citation_from_a_callback_is_rejected` | pass |
| 12 | authorized user unaffected by another user's revocation | `test_authorized_user_keeps_working_after_another_user_is_revoked` | pass |
| 13 | `access_snapshot` returns one consistent live doc+group read | `test_access_snapshot_reports_live_documents_and_groups` | pass |
| 14 | cache/projection scope isolation | `test_cache_and_projection_are_scope_isolated` | pass |
| 15 | second store instance observes commits and external revoke | `test_a_second_store_instance_observes_commits_and_revocations` | pass |
| 16 | stale-generation plan rejected, no partial writes | `test_stale_generation_plan_is_rejected_without_partial_writes` | pass |
| 17 | a plan from one scope cannot write into another | `test_a_plan_built_for_one_scope_cannot_write_into_another` | pass |
| 18 | content edit invalidates a still-authorized cached answer | `test_edit_invalidates_a_cached_answer_even_when_still_authorized` | pass |

No hidden text (restricted body, old body, or cross-tenant body) appears in any
full JSON response. Assertions scan the whole serialized response (`answer`,
`evidence` quotes/ids, and any other key), not just the `answer` field.

## 4. Verified guarantees (no defects against the shared contract)

Store:

- Scope is part of every primary key; identical `document_id` values stay
  distinct across tenants, in live docs, projection, and cache.
- Same-revision ACL/metadata re-observation is a real upsert because
  `document_fingerprint` includes ACL, and it replaces the live row in one
  transaction.
- Generation is stored **per scope and source**; a plan built from one scope's
  state is rejected for another scope (current generation `0` vs expected `1`).
- Stale `expected_generation` is rejected before any document/projection/state
  write; the previous committed value survives.
- Independent store instances on the same file observe each other's committed
  documents, groups, and cache (fresh connection per request).
- `access_snapshot` reflects live ACL and membership in one read transaction.

Engine (`CompanyBrain`):

- Authorization is recomputed from the store on every request; no constructor
  state is trusted.
- `public` and `connector_scope` are tenant-visible; `restricted` requires a
  current matching `team` group or matching `user` principal. Verified for a
  public→restricted transition and for group removal.
- Cached answers are revalidated against the current authorized fingerprint,
  cited revisions, `content_digest`, and quote presence before being served, so
  a same-revision ACL change, group removal, edit, or deletion forces a
  regenerate/abstain (`cache_hit=False`).
- Generated output is validated with `parse_answer` against only authorized
  documents; a callback that cites a hidden document gets an abstention with no
  hidden text.
- The generator is re-run and the authorized snapshot is re-read after the
  callback; a group revoke or source edit performed during generation is not
  served.
- Cache keys are per `(scope, question, user_id)`, so one user's revocation does
  not evict or leak another user's answer.

## 5. Defects vs host responsibilities

### D1 (limitation, host responsibility): uncited prose can carry hidden text

Not a violation of the literal contract, but recorded because the task asked to
verify "no hidden text appears". If a callback returns an `answer` string that
contains hidden content while citing only an authorized document:

```
answer = <hidden body>
evidence = [{"document_id": <authorized public doc>, "quote": <public body>}]
```

`parse_answer` accepts it (it validates citations, not that the answer text is
derived from them), and the engine serves the answer verbatim. Confirmed with a
direct probe:

```
PROSE_SMUGGLE hidden_in_response: True
response: {'answer': 'The Nimbus secret refund ceiling is 9999999 credits.',
           'disposition': 'grounded', ... 'cache_hit': False}
```

Why this is a host responsibility, not an engine bug: the callback receives only
authorized documents, so a genuine model cannot know restricted content that was
never in its context. The shared contract requires "do not allow a callback to
cite hidden sources" and rechecks before serving; both hold. The engine
guarantees citation authorization, not semantic grounding of arbitrary prose.
No failing test was added for this because asserting it would exceed the shared
contract and would keep another owner's file red for an out-of-scope
requirement. It is documented here with an optional hardening below.

Related, lower-severity: `CompanyBrain._generate` catches only
`MalformedModelOutput`. `parse_answer` can also raise `ValueError` (e.g. for
conflicting duplicate `document_id`s). Within one scope the store's primary key
makes that unreachable, so no test triggers it.

## 6. Exact recommended fixes

F1 (optional hardening for D1, engine owner's call). Add an explicit grounding
gate so unsupported prose cannot be served, without rejecting legitimate
paraphrase by default:

```python
# engine.py
from mari_kit.knowledge.scoring import grounding_coverage

ANSWER_GROUNDING_FLOOR = 0.5  # configurable; 0.0 disables

def _grounded(self, grounded, current, question, user_id):
    if grounding_coverage(grounded.answer, grounded.evidence) < ANSWER_GROUNDING_FLOOR:
        return self._abstention(question, user_id)
    ...
```

Expose the floor on `CompanyBrain.__init__` (e.g. `answer_grounding_floor`) so
hosts that accept paraphrases can set it to `0.0`, and document that the
default engine guarantee is citation authorization only.

F2 (defensive, same module). Broaden the generation error boundary to
`except (MalformedModelOutput, ValueError)` so a malformed documents set cannot
escape as an exception. Keep the abstention uncached (`malformed=True`) so a
corrected callback can succeed next request.

F3 (docs, not code). State the trust boundary in the durable README/engine
docstring: the generator is host-supplied and receives only authorized
documents; the engine prevents unauthorized citations and stale/revoked serving,
but does not attest that arbitrary answer prose is entailed by its citations.

## 7. Limitations / not covered

- Cache reuse is per `(scope, question, user_id)`; cross-user cache sharing is
  neither required nor assumed, and no test asserts it.
- No crash/failpoint (`os._exit`) testing here; that belongs to the durability
  breaker. Generation/transaction atomicity under kill was not re-probed.
- Concurrency stress (parallel writers racing `BEGIN IMMEDIATE`) was not run;
  only sequential cross-instance visibility was verified.
- `connector_scope` tenant visibility is exercised indirectly (the policy is
  read from `engine.py`); the corpus does not include a `connector_scope`
  fixture.
- Live model calls were not made; all generators are deterministic local
  callbacks, as required.

## 8. Integration note

`tests/test_brain2_revocation.py` imports
`examples.company_brains.durable.store` and
`examples.company_brains.durable.engine` at module import time. It will fail to
collect if either module is renamed or moved; that is intentional coupling to
the shared contract's named artifacts. Coordinator may run the file as-is with
`.venv/bin/python -m pytest tests/test_brain2_revocation.py -q`.
