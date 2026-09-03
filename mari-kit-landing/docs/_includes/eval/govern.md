:::{admonition} Benchmark first
:class: benchmark
**Corpora:** [FEVER](https://fever.ai/) · [FEVEROUS](https://github.com/Raldir/FEVEROUS) · [ContraDoc](https://github.com/ddhruvkr/CONTRADOC) · [FreshQA](https://github.com/freshllms/freshqa)

**Protocol:** Report verdict macro-F1 and accuracy separately from evidence precision/recall/F1 and contradiction localization. Pin corpus and source revisions. Replay corrections and removals, then measure stale-answer rate, time-to-consistency, unsupported-answer rate, and authorization leakage. A correct label without the complete evidence set does not pass the evidence contract.
:::
