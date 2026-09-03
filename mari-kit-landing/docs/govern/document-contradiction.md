[]{#document-contradiction}[Current]{.current-label}

# Document-level self-contradiction detection

## At a glance

| Layer | Mari provides | Caller provides |
|---|---|---|
| Judgment validation | Positive/negative shape rules and sentence bounds | Semantic contradiction judgment |
| Localization | Evidence IDs and overlap accounting | Candidate evidence sentences |
| Reference coverage | Parsed reasoning citations and reward component | Reasoning text |
| Training reward | Separate accuracy, coverage, and format signals | Optimizer and training loop |

ContraDoc model quality is separate from these deterministic semantics because the judge model—not Mari’s validator—determines detection quality.

| Observed judge behavior | Result | What it means |
|---|---:|---|
| Contradiction accuracy | `0.694` | The injected judge is usable as a baseline, not a production claim |
| Macro-F1 | `0.685` | Positive and negative documents are both represented in the balanced slice |
| Evidence localization recall | `0.388` | Correctly finding the conflicting sentences remains the main weakness |

These results use `deepseek-chat` on a fixed 160-document ContraDoc slice. The predictions are retained because the model alias itself is not an immutable checkpoint.


:::{collapse} Worked reward examples

| Expected | Predicted | Evidence hit | Accuracy reward |
|---|---|---:|---:|
| Contradiction | Contradiction | Yes | `1 + matched / gold` |
| Contradiction | Contradiction | No | `-1` |
| No contradiction | No contradiction | Not applicable | `1` |
| No contradiction | Contradiction | Not applicable | `0` |
:::

:::::::{container} diagram flow
::: card
**Tagged document**[\[1\] ... \[2\] ... \[n\]]{.small}
:::

*model*

::: card
**Judgment + evidence**[reasoning references]{.small}
:::

*validate*

::: card
**Assessment**[localized + coverage]{.small}
:::

*train/evaluate*

::: card
**Reward components**[accuracy · coverage · format]{.small}
:::
:::::::

```{code-block} python
:caption: document_contradiction.py

from mari_components.verification import (
    document_contradiction_rewards, validate_document_contradiction,
)

assessment = validate_document_contradiction(
    sentence_count=len(sentences), judgment=proposal.judgment,
    evidence_sentence_ids=proposal.evidence_sentence_ids,
    reasoning=proposal.reasoning,
)
rewards = document_contradiction_rewards(
    assessment, expected_judgment=case.is_self_contradictory,
    gold_evidence_sentence_ids=case.conflicting_sentence_ids,
    format_valid=proposal.matches_required_format,
)
```

**What Mari does not claim.** Reference coverage measures which sentence tags appeared in reasoning; it does not prove the reasoning is valid. Mari validates and scores a proposed judgment but does not replace the teacher-distilled SFT model, GRPO trainer, or semantic contradiction verifier.

::: source-block
**Papers**

[Reinforced Reference Coverage for Document-Level Self-Contradiction Detection](https://aclanthology.org/2025.emnlp-main.67/){.paper}[ContraDoc benchmark](https://arxiv.org/abs/2311.09182){.paper}

[Mari implements sentence-reference parsing, localization invariants, Equation 7 coverage, and Equations 5--8 reward components. These were checked against the MIT RRC-DSCD implementation and Apache-2.0 ContraDoc boundary. The RRC repository's current accuracy code diverges from published Equation 5: it normalizes by predicted evidence and produces a 0.5 zero-hit score. Mari deliberately retains the paper's gold-normalized term and -1 zero-hit result.]{.small}
:::


This is not corpus retrieval. It validates whether one multi-sentence document is judged to contradict itself, where the conflict occurs, how much of the document the reasoning inspected, and how an external reinforcement-learning trainer should score the result.

## How it works

1.  **Tag sentences.** Number the document from 1 through `n` before inference.
2.  **Propose a judgment.** An injected model returns a Boolean judgment, localized evidence sentence IDs, and reasoning containing `[i]`, `[i-j]`, or `[i]-[j]` references.
3.  **Validate localization.** Mari expands ranges, rejects out-of-document references, requires evidence for positive judgments, and forbids contradiction evidence on negative judgments.
4.  **Measure reference coverage.** Deduplicate every sentence mentioned in reasoning and compute `|S_covered| / |S_total|`.
5.  **Compute independent rewards.** Return accuracy, reference-coverage, and format components for an external GRPO trainer. A correct positive judgment without any gold-evidence hit receives `-1`; a correct localized judgment receives `1 + matched/gold`.
