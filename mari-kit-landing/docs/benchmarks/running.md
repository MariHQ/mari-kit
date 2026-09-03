# Running an evaluation

The public runner downloads checksum-pinned SciFact and LongMemEval-S artifacts, invokes Mari's implementations, and writes aggregate JSON plus a JSONL row for every query.

```console
$ python benchmarks/run_public.py all
$ python benchmarks/verify_results.py
verified 3 reports and 962 case records
```

Run one layer while iterating:

```console
$ python benchmarks/run_public.py scifact
$ python benchmarks/run_public.py indexes
$ python benchmarks/run_public.py longmemeval
```

`benchmarks/data/` is ignored. `benchmarks/results/` is committed so a claimed score can be audited without downloading a corpus. Each report records its corpus checksum, exact configuration, Mari commit, Python and NumPy versions, platform, build time, and latency distribution.

## Score a ranked run

Create JSONL with one query per line. IDs must be the corpus IDs, not array positions.

```json
{"query_id":"q1","ranked_ids":["d2","d1"],"relevance":{"d1":2,"d2":1}}
{"query_id":"q2","ranked_ids":["d8","d4"],"relevance":{"d4":1}}
```

The generic scorer is useful for an external system's ranked run. It is not itself a benchmark until those rows came from a pinned public corpus.

## Compare the right layer

For an index change, freeze parsed passages and compare candidate recall, final ranking, latency, and bytes. For a parser change, score structure first and then rebuild the same index. For a memory policy change, freeze the answer model and context budget. For an evidence-policy change, keep retrieval results fixed. This isolates the component responsible for a movement.

## Regression gate

A gate contains a minimum quality threshold and maximum resource budget. It also contains invariants: no unauthorized ID may enter candidates, evidence IDs must resolve to the pinned source revision, deleted records must disappear after replay, and repeated execution with a deterministic component must produce the same report.
