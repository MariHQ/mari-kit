:::{admonition} Benchmark first
:class: benchmark
**Corpora:** [BEIR](https://github.com/beir-cellar/beir), [FEVER](https://fever.ai/), and [LongMemEval](https://github.com/xiaowu0162/LongMemEval) form the end-to-end matrix; deterministic fixture suites cover stores, serialization, compiler output, and failure recovery.

**Protocol:** Pin every input, dependency, model, prompt, and seed. Preserve per-case traces and report quality beside p50/p95 latency, tokens, storage, index-build time, refresh work, and failure count. Compare outputs after restart and across supported stores; compiled configurations must reproduce the same artifact graph and evaluator inputs.
:::
