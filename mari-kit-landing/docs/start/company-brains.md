[]{#company-brains}[Supported composition]{.current-label}

# Company brains

## Scenarios

From an installed repository checkout:

```{code-block} console
python -m examples.company_brains
python -m examples.company_brains.durable
```

Eight scenarios compose Mari's public APIs into small company knowledge
applications. Each uses synthetic documents and deterministic model output.
The scenarios run offline with no credentials. The combined runner emits JSON
with each scenario's observable results.

| Scenario | Workflow |
|---|---|
| `search` | Cross-source search, cited answers, edits, and deletion |
| `support` | Reviewed answer reuse, changed policies, and revoked access |
| `onboarding` | Employee policy facts and section-level evidence freshness |
| `incident` | Runbook dependencies and selective invalidation |
| `decisions` | Decision evidence, review, and revision history |
| `conversation` | Conversation extraction, caching, and source evidence |
| `sync` | Paginated snapshots, incremental changes, and transaction generations |
| `isolation` | Tenant-scoped identities and per-user access boundaries |

## Persistent application

The durable example is a host-owned reference application built on Python's
SQLite driver. It keeps live documents, a search projection, sync state,
memberships, and answer caches across restarts. Mari remains backend-agnostic.

```{code-block} python
:caption: A restart-safe, permission-aware answer path (condensed)

from mari_kit import PollPage, ScopeRef, SyncMode
from mari_kit.sync import plan_sync

scope = ScopeRef(tenant="acme", space="company")

with SQLiteBrainStore(path) as store:
    plan = plan_sync(store.state(scope, "handbook"),
        PollPage(upserts=documents, snapshot_complete=True),
        source_id="handbook", mode=SyncMode.FULL)
    store.apply_plan(scope, plan)
    store.set_groups(scope, "alice", ("support",))

    brain = CompanyBrain(store, scope, view_cache_size=8)
    answer = brain.answer("What is the refund window?",
        user_id="alice", generate=model_callback)
```

| Guarantee | Mechanism |
|---|---|
| Atomic sync | Documents, projection, and checkpoint commit in one transaction with an optimistic generation check |
| Current authorization | Live access counters are checked on every request and again after the model callback |
| Safe answer reuse | Cached answers require matching authorized source observations. Edits, deletions, and ACL changes invalidate them |
| Bounded memory | Authorized views and indexes are cached by count and optional byte budget |
| Crash recovery | Process-death tests cover each write stage. A fresh process resumes from the persisted checkpoint |

Authentication, identity provisioning, backup and restore, encrypted storage,
and deployment remain application responsibilities. The atomicity tests
exercise process death on one SQLite database. Power loss and distributed
databases are outside their scope.

:::{collapse} Evaluation and benchmarks

Fixture evaluation covers current and superseded policy, unresolved conflicts,
ambiguous questions, missing information, restricted evidence, and irrelevant
matches. Opt-in live evaluation sends only synthetic questions and authorized
source revisions to a model. Exact citation validation and lexical grading
check quotations and wording. Semantic entailment needs separate evaluation.

Scale, recall, filtered-recall, multi-start, and cache-memory benchmarks live
in `benchmarks/company_brain_*.py`. They identify where a production search
adapter is warranted. Production service levels need measurement on the
target deployment.
:::

## Extend the composition

Replace `SQLiteBrainStore` with an application store that maintains the same
access counters, or returns opaque access tokens with equivalent meaning.
Replace the reference BM25 view with a production index. Use
[HNSW filtered search](../retrieve/retrieval.md) controls when authorization
allowlists are small.
