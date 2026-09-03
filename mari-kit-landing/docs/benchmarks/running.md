# Running an evaluation

:::{admonition} Benchmark first
:class: benchmark
Begin with BEIR SciFact: it is small enough for a development loop and jointly tests ranking against scientific evidence judgments. Add ArguAna for opposition retrieval, then one large and one out-of-domain BEIR task before treating a retrieval change as general.
:::

## Score a ranked run

Create JSONL with one query per line. IDs must be the corpus IDs, not array positions.

```json
{"query_id":"q1","ranked_ids":["d2","d1"],"relevance":{"d1":2,"d2":1}}
{"query_id":"q2","ranked_ids":["d8","d4"],"relevance":{"d4":1}}
```

```console
$ python benchmarks/evaluate_retrieval.py results/scifact.jsonl --k 10
{
  "k": 10,
  "mrr": 0.75,
  "ndcg": 0.7138,
  "precision": 0.15,
  "queries": 2,
  "recall": 1.0
}
```

## Compare the right layer

For an index change, freeze parsed passages and compare candidate recall, final ranking, latency, and bytes. For a parser change, score structure first and then rebuild the same index. For a memory policy change, freeze the answer model and context budget. For an evidence-policy change, keep retrieval results fixed. This isolates the component responsible for a movement.

## Regression gate

A gate contains a minimum quality threshold and maximum resource budget. It also contains invariants: no unauthorized ID may enter candidates, evidence IDs must resolve to the pinned source revision, deleted records must disappear after replay, and repeated execution with a deterministic component must produce the same report.
