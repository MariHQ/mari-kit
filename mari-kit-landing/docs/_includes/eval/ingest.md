:::{admonition} Benchmark first
:class: benchmark
**Corpora:** [QASPER](https://allenai.org/data/qasper) · [WikiSection](https://github.com/sebastianarnold/WikiSection) · [DocRED](https://github.com/thunlp/DocRED). Connectors use recorded provider fixtures because public content corpora do not test cursors, deletes, retries, or event ordering.

**Protocol:** Score text preservation, section Boundary F1/Pk/WindowDiff, entity/relation F1, stable-ID rate, duplicate rate, and incremental/full-sync equivalence. For polling and streaming, replay the same create→update→delete trace with injected duplicates, reordering, throttling, and cursor expiry; the final snapshot and emitted change set must agree.
:::
