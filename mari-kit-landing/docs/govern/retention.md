[]{#retention}[Supported]{.current-label}

# Retention, deletion, and purpose

## Contract

| Knowledge | Policy | At evaluation time | Result |
|---|---|---|---|
| Session transcript | 30-day TTL | 31 days old | Expire and remove from retrieval |
| Derived preference | Depends on transcript | Parent deleted | Tombstone and invalidate projection |
| Compliance evidence | Seven-year retention | User requests ordinary deletion | Hold. Record policy reason |
| Support address | Purpose: order fulfillment | Marketing retrieval | Deny for incompatible purpose |

## How it works

Retention and freshness produce independent decisions. `plan_retention`
emits delete actions for expired records, hold actions for expired held
records, and invalidations for reachable derivatives. Each action contains
the record ID, kind, and reason. The host persists its own tombstones and event
times, removes content from reads, and applies storage retention policy.

```{code-block} python
:caption: Plan deletion through derivation edges

from datetime import datetime, timezone

from mari_components.governance import RetentionPolicy, plan_retention

plan = plan_retention(
    records=records,
    dependencies=dependencies,
    now=datetime.now(timezone.utc),
    policy=RetentionPolicy(
        default_ttl_days=30,
    ),
)

for action in plan.actions:
    store.apply_retention(action)
```

Mari produces a plan. The storage adapter performs physical deletion.
Database-specific erasure and legal policy stay outside the core. Mari's
dependency records keep that part testable.

`dependencies` maps each parent record ID to its derived child IDs. A held
child can still receive an invalidation when its parent expires. Invalidation
marks derived work unusable and physical preservation remains the host's job.
Repeated calls return deterministic actions. Persist applied-action identity
in the host to make effects idempotent.

Purpose checks use `evaluate_purpose(record, requested_purpose=...)` and the
record's `purposes` tuple. Apply that decision before retrieval.
`RetentionPolicy.allowed_purposes` is currently stored configuration and is
independent of the expiration planner's decisions.

## Measures

| Invariant | Expected result |
|---|---|
| Expired artifact retrieval | Zero returned content |
| Dependency cascade | Every reachable derivative invalidated |
| Legal hold | Held expired record receives `HOLD` in place of `DELETE` |
| Purpose mismatch | Access denied before ranking |
| Repeated planning | Same actions for the same inputs. Host deduplicates effects |

::: source-block
**Papers and implementations**

[Machine unlearning survey](https://arxiv.org/abs/2306.03558){.paper}[SISA training](https://arxiv.org/abs/1912.03817){.paper}[Portable Memory tombstones](https://github.com/MacPaw/portable-memory){.paper}[GDPR Article 5](https://eur-lex.europa.eu/eli/reg/2016/679/oj){.paper}

[Model-weight unlearning is outside Mari. The relevant mechanism is deletion from stores, indexes, bundles, and derived knowledge.]{.small}
:::
