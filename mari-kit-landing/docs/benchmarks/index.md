# Benchmarks and evaluations

:::{admonition} Benchmark first
:class: benchmark
The initial public suite is [BEIR](https://github.com/beir-cellar/beir) for retrieval, [FEVER](https://fever.ai/) and [QASPER](https://allenai.org/data/qasper) for evidence, [WikiSection](https://github.com/sebastianarnold/WikiSection) and [DocRED](https://github.com/thunlp/DocRED) for structure, [ContraDoc](https://github.com/ddhruvkr/CONTRADOC) for self-contradiction, [WDC Products](https://webdatacommons.org/largescaleproductcorpus/wdc-products/) for resolution, and [LongMemEval](https://github.com/xiaowu0162/LongMemEval) for memory.
:::

Mari evaluates stages before end-to-end answers. A weak final score can originate in parsing, retrieval, evidence selection, policy, context packing, or generation; one aggregate number cannot distinguish them.

## Run contract

```python
from mari_components.evaluation import (
    evaluate_retrieval,
    load_catalog,
    load_suite_catalog,
)

catalog = load_catalog("benchmarks/catalog.json")
suites = load_suite_catalog("benchmarks/suites.json")
case_score = evaluate_retrieval(
    ranked_ids=["passage-7", "passage-2", "passage-9"],
    relevance={"passage-2": 2.0, "passage-7": 1.0},
    k=10,
)
print(case_score.ndcg, case_score.recall)
```

Every persisted run identifies the corpus revision and split, Mari commit, configuration, seed, model and prompt identifiers, environment, wall time, token counts, and per-case outputs. Dataset artifacts remain outside Git.

## Evaluation path

:::{container} diagram benchmark-flow
frozen corpus *→* adapter *→* Mari stage *→* predictions + traces *→* deterministic metrics *→* regression gate
:::

## Corpus catalog

| Capability | Primary corpus | Primary measurements |
|---|---|---|
| Retrieval and indexes | BEIR, LoTTE | nDCG@10, Recall@100, MRR, latency, index bytes |
| Parsing and sections | QASPER, WikiSection | text preservation, Boundary F1, Pk, WindowDiff |
| Evidence and verification | FEVER, FEVEROUS, QASPER | evidence F1, verdict accuracy, answer F1 |
| Contradictions | ContraDoc, BEIR ArguAna | macro-F1, localization F1, contradiction Recall@k |
| Graph construction | DocRED, QASC | relation F1, provenance recall, multi-hop accuracy |
| Entity resolution | WDC Products | pair/cluster F1, pairs completeness, reduction ratio |
| Freshness | FreshQA plus revision replay | strict accuracy, stale-answer rate, time-to-consistency |
| Memory | LongMemEval | accuracy by capability, evidence Recall@k, reader tokens |
| Context assembly | LongBench, QASPER | score by length and budget, evidence density |

## Licensing boundary

The catalog records access and license notes but does not download anything. Benchmark code and benchmark data can have different licenses, and aggregate suites such as BEIR and LongBench retain the terms of their constituent datasets. Review upstream terms before local caching, derived-data publication, or commercial use.

```{toctree}
:maxdepth: 1
:hidden:

running
suites
reference-validation
```
