:::{admonition} Benchmark first
:class: benchmark
**Corpora:** [BEIR](https://github.com/beir-cellar/beir) (SciFact, ArguAna, HotpotQA) · [LoTTE](https://github.com/stanford-futuredata/ColBERT) · [KILT](https://github.com/facebookresearch/KILT)

**Protocol:** Build from corpus documents only; issue the published test queries; preserve ranked IDs and component scores. Report nDCG@10, Recall@100, MRR, p50/p95 query latency, index bytes, and results with ACL pre-filtering. Ablate candidate generation, reranking, fusion, graph expansion, and packing independently.
:::
