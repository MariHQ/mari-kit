[]{#graph}[Proposed]{.proposed-label}

# Bi-temporal knowledge graph

Statements would track valid time (when the claim applied) and transaction time (when the system learned it), supporting historical queries and late corrections.

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
:caption: proposed / graph.py

graph.assert_fact(subject="plan:enterprise", predicate="refund_window_days",
    object=30, valid_time=Interval("2026-01-01", "2026-08-31"),
    transaction_time=clock.now(), evidence=evidence)

then = graph.query(at="2026-06-01", known_at="2026-09-01")
now = graph.query(at=clock.now(), known_at=clock.now())
```
