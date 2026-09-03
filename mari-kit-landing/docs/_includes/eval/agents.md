:::{admonition} Benchmark first
:class: benchmark
**Corpora:** [KILT](https://github.com/facebookresearch/KILT), [QASC](https://github.com/allenai/qasc), and [LongMemEval](https://github.com/xiaowu0162/LongMemEval), plus repository-owned golden tool traces for workflow replay.

**Protocol:** Separate retrieval/evidence quality from agent execution. Report task success, exact and partial tool-sequence match, argument validity, tool-error recovery, grounded-output rate, trajectory cost, and reused-procedure uplift. Evaluate mined procedures on held-out tasks and reject any train/test source overlap.
:::
