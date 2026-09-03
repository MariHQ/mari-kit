[]{#document-contradiction}[Current]{.current-label}

# Document-level self-contradiction detection

## Evaluation

Six document-level cases measure sentence-range expansion, reference coverage, positive and negative rewards, zero-hit penalties, evidence validation, and localization. The numerical reward and range fixtures are compared with the MIT RRC-DSCD implementation where it agrees with the published equations. ContraDoc macro-F1 and localization F1 have not been run; no detector-quality claim is made.

```console
$ pytest -q tests/test_contradiction_algorithms.py -k DocumentSelfContradiction
6 passed
```

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

**What Mari does not claim**Reference coverage measures which sentence tags appeared in reasoning; it does not prove the reasoning is valid. Mari validates and scores a proposed judgment but does not replace the teacher-distilled SFT model, GRPO trainer, or semantic contradiction verifier.

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

:::::::{container} diagram flow
::: card
**Tagged document**[\[1\] ... \[2\] ... \[n\]]{.small}
:::
