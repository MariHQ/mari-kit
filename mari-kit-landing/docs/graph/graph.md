[]{#graph}[Current]{.current-label}

# Bi-temporal knowledge graph

```{include} ../_includes/eval/graph.md
```

`TemporalFact` tracks valid time (when a claim applies) and transaction time (when the system knows it), supporting historical queries and late corrections.

## How it works

An assertion is append-only and carries two intervals. A correction learned today may close an older assertion's transaction interval while preserving its historical valid interval. Query `at` filters valid time; `known_at` filters transaction time; both must contain their requested timestamp. Contradictions create explicit edges or superseding revisions instead of destructive overwrites.

**Research basis**[Zep](https://arxiv.org/abs/2501.13956){.paper} uses a temporally aware graph to maintain historical relationships for agent memory, while the [temporal knowledge-graph survey](https://arxiv.org/abs/2201.08236){.paper} catalogs representations and inference tasks for facts that change over time. Mari adds explicit valid-time and transaction-time query semantics; interval boundaries and contradiction policy require conformance tests.

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
