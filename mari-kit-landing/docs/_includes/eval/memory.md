:::{admonition} Benchmark first
:class: benchmark
**Corpora:** [LongMemEval](https://github.com/xiaowu0162/LongMemEval) · [QASPER](https://allenai.org/data/qasper) · [LongBench](https://github.com/THUDM/LongBench)

**Protocol:** Replay sessions in timestamp order without gold-answer fields. Report information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention separately; add evidence Recall@k, write amplification, stored bytes, reader tokens, and latency. Compare raw-history, retrieval-only, extracted-memory, and consolidated-memory baselines under identical context budgets.
:::
