[]{#retention}[Current]{.current-label}

# Retention, deletion, and purpose

## Contract

| Knowledge | Policy | At evaluation time | Result |
|---|---|---|---|
| Session transcript | 30-day TTL | 31 days old | Expire and remove from retrieval |
| Derived preference | Depends on transcript | Parent deleted | Tombstone and invalidate projection |
| Compliance evidence | Seven-year retention | User requests ordinary deletion | Hold. Record policy reason |
| Support address | Purpose: order fulfillment | Marketing retrieval | Deny for incompatible purpose |

## How it works

Retention and freshness produce independent decisions. Expiration removes
knowledge from ordinary reads. A tombstone records identity and reason. It also
keeps the event time and reachable derived artifacts. Deleted content leaves
the record. Legal holds take priority over routine expiration and remain
visible in the decision trace.

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
        allowed_purposes={"support": ("order_fulfillment",)},
    ),
)

for action in plan.actions:
    store.apply_retention(action)
```

Mari produces a plan. The storage adapter performs physical deletion.
Database-specific erasure and legal policy stay outside the core. Mari's
dependency records keep that part testable.

## Measures

| Invariant | Expected result |
|---|---|
| Expired artifact retrieval | Zero returned content |
| Dependency cascade | Every reachable derivative invalidated |
| Legal hold | No destructive action emitted |
| Purpose mismatch | Access denied before ranking |
| Repeated planning | Same idempotency keys and zero duplicate deletions |

::: source-block
**Papers and implementations**

[Machine unlearning survey](https://arxiv.org/abs/2306.03558){.paper}[SISA training](https://arxiv.org/abs/1912.03817){.paper}[Portable Memory tombstones](https://github.com/MacPaw/portable-memory){.paper}[GDPR Article 5](https://eur-lex.europa.eu/eli/reg/2016/679/oj){.paper}

[Model-weight unlearning is outside Mari. The relevant mechanism is deletion from stores, indexes, bundles, and derived knowledge.]{.small}
:::
