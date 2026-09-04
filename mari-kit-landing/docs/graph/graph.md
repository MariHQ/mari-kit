[]{#graph}[Reference]{.current-label}

# Bi-temporal knowledge graph

## Behavior

| LongMemEval temporal check | Result | Meaning |
|---|---:|---|
| Gold-session provenance visible at question time | `0.936` | Some gold session IDs are absent or timestamp-incompatible in the cleaned records |
| Future-session exclusion | `1.000` | The bitemporal filter excluded every session dated after the question |

The reported value measures visibility semantics. Model answer quality has its
own measure.

:::{collapse} Example bitemporal difference

| Query | Valid at requested time | Known at requested time | Returned |
|---|---:|---:|---:|
| Historical state before correction arrived | Yes | Yes | Original fact |
| Same valid date, knowledge after correction | Yes | No for original revision | Corrected fact |
| Timestamp equals half-open interval end | No | n/a | Excluded |
:::



`TemporalFact` tracks valid time (when a claim applies) and transaction time (when the system knows it), supporting historical queries and late corrections.

## How it works

An assertion is append-only and carries two intervals. A correction learned
today closes an older assertion's transaction interval. Its historical valid
interval remains in the record. Query `at` filters valid time. Query `known_at`
filters transaction time. Each interval must contain its requested timestamp.
Contradictions create explicit edges or superseding revisions. Prior revisions
stay available.

**Research basis**[Zep](https://arxiv.org/abs/2501.13956){.paper} uses a
temporally aware graph to maintain historical relationships for agent memory.
The [temporal knowledge-graph survey](https://arxiv.org/abs/2201.08236){.paper}
catalogs representations and inference tasks for facts that change over time.
Mari adds explicit valid-time and transaction-time query semantics.
Applications choose interval boundaries and contradiction policies for their
domain.

:::::{container} diagram bitemporal
<div>

**valid time**Jan ───────── Aug

</div>

<div>

**transaction time**learned Sep 01 ───▶

</div>
:::::

```{code-block} python
:caption: Half-open valid-time and transaction-time queries

from datetime import datetime, timezone

from mari_components.graph import TemporalFact, query_temporal_facts

utc = timezone.utc
facts = [
    TemporalFact(
        fact_id="refund-window@1",
        subject="plan:enterprise",
        predicate="refund_window_days",
        object=30,
        valid_from=datetime(2026, 1, 1, tzinfo=utc),
        valid_to=datetime(2026, 9, 1, tzinfo=utc),
        recorded_from=datetime(2026, 1, 3, tzinfo=utc),
    )
]

visible = query_temporal_facts(
    facts,
    at=datetime(2026, 6, 1, tzinfo=utc),
    known_at=datetime(2026, 8, 1, tzinfo=utc),
)
```
