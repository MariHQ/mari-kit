[]{#verification}[Current]{.current-label}

# Verification portfolios

```{include} ../_includes/eval/govern.md
```

Verification functions score already-parsed values and retain all successful attempts and failures for audit.

## How it works

`best_of_n` calls the producer up to `n` times, parses each output, records parse failures without discarding successful siblings, scores valid candidates, and selects the highest score with stable first-wins ties; it may stop once the threshold is met. `verdict_consensus` counts typed verdicts rather than free text. Grounding scores combine declared deterministic components; they are used for ranking or abstention, never calibrated as probabilities.

```{code-block} python
:caption: verify.py

from mari_components.verification import best_of_n, score_grounded

result = best_of_n(
    lambda: model(question, documents),
    lambda raw: parse_answer(question, documents, raw),
    lambda answer: score_grounded(answer,
        required_ideas=("eligibility", "time limit")),
    attempts=3, threshold=0.90)

audit(result.selected, result.attempts, result.failures, result.stopped_early)
```

:::::::: cards
::: card
`select_best`

Scores existing candidates with stable tie-breaking.
:::

::: card
`verdict_consensus`

Aggregates supported, contradicted, and uncertain assessments.
:::

::: card
`score_grounded`

Evidence, coverage, completeness, corroboration, certainty.
:::

::: card
`harmonic_score`
:::

::: card
`idea_completeness`
:::
::::::::

**Scores are not truth probabilities.**They are deterministic quality signals for selection and abstention.

::: source-block
**Research basis**

[Self-consistency improves chain-of-thought reasoning](https://arxiv.org/abs/2203.11171){.paper}[FEVER: evidence-based verification](https://arxiv.org/abs/1803.05355){.paper}[ALCE: citation quality evaluation](https://arxiv.org/abs/2305.14627){.paper}

[Mari exposes an auditable selection portfolio; it does not reproduce model sampling or benchmark metrics.]{.small}
:::
