# Mari benchmarks

Benchmarks are feature contracts, not a leaderboard. Every run preserves the corpus revision, split, Mari commit, configuration, random seed, model identifiers, latency, token use, and per-case outputs.

`catalog.json` records candidate public corpora without downloading them or accepting their terms. A repository license does not necessarily cover embedded source documents. Review the declared dataset terms before caching or redistributing a corpus.

## First profiles

- Retrieval: BEIR SciFact, ArguAna, and a domain-diverse slice; report nDCG@10, Recall@100, MRR, p50/p95 latency, and index size.
- Evidence: FEVER and QASPER; report verdict or answer quality separately from evidence-set precision and recall.
- Structure: WikiSection and DocRED; report boundary, entity, and relation metrics before downstream QA.
- Memory: cleaned LongMemEval; report each capability, retrieval recall, end-to-end accuracy, context tokens, and update or abstention failures.
- Freshness: a pinned FreshQA revision plus synthetic source revisions; report strict accuracy by question type and time since change.

## Catalog access

```python
from mari_components.evaluation import load_catalog

catalog = load_catalog("benchmarks/catalog.json")
for corpus in catalog.for_task("evidence-retrieval"):
    print(corpus.name, corpus.metrics, corpus.license)
```

## Retrieval run format

The deterministic runner consumes one JSON object per query. `relevance` may contain binary or graded judgments.

```json
{"query_id":"q1","ranked_ids":["d2","d1"],"relevance":{"d1":2,"d2":1}}
```

```shell
python benchmarks/evaluate_retrieval.py run.jsonl --k 10
```

Public corpora are not committed here. Put local copies under `benchmarks/data/`; that path is ignored by Git.
