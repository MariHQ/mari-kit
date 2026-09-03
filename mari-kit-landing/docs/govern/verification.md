[]{#verification}[Current]{.current-label}

# Verification portfolios

## At a glance

| Mechanism | Protects against | Does not establish |
|---|---|---|
| Best-of-N | A single poor sampled candidate | Correctness when every scorer is wrong |
| Verdict consensus | One unstable judgment | Independence between judges |
| Grounding score | Unsupported required ideas | Truth beyond the supplied evidence |
| Selection trace | Opaque winner choice | Calibration of injected scores |


:::{collapse} Worked consensus example

| Candidate | Evidence weight | Verdict |
|---|---:|---|
| A | 0.70 | Supported |
| B | 0.20 | Contradicted |
| C | 0.10 | Uncertain |

The selected verdict is supported. Equal supported and contradicted weight produces abstention instead of arbitrary tie-breaking.
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

**Scores are not truth probabilities.** They are deterministic quality signals for selection and abstention.

## Numerical evidence without a conclusion policy

`weighted_mean` returns normalized weights and each observation's numerical
contribution. `wilson_proportion` returns a finite point estimate and interval
for caller-labeled binary outcomes. Neither function names an outcome good,
selects an action, or converts uncertainty into a verdict.

```{code-block} python
:caption: Preserve outcome uncertainty as ranking features

from mari_components.knowledge import WeightedObservation, weighted_mean, wilson_proportion

estimate = weighted_mean([
    WeightedObservation(observation_id="study-a", value=0.20, weight=2.0),
    WeightedObservation(observation_id="study-b", value=-0.10, weight=1.0),
])

success_rate = wilson_proportion(successes=7, total=10)
assert success_rate.level == 0.95
```

| Output | What it says | What it does not say |
|---|---|---|
| Contribution `0.133` | Observation A's weighted contribution | That A is independent or authoritative |
| Interval containing `0.70` | Sampling uncertainty under a binomial model | That the next remediation should run |

[Wilson score interval](https://doi.org/10.1080/01621459.1927.10502953){.paper}[Cochrane statistical methods](https://training.cochrane.org/handbook/current/chapter-10){.paper}

::: source-block
**Research basis**

[Self-consistency improves chain-of-thought reasoning](https://arxiv.org/abs/2203.11171){.paper}[FEVER: evidence-based verification](https://arxiv.org/abs/1803.05355){.paper}[ALCE: citation quality evaluation](https://arxiv.org/abs/2305.14627){.paper}

[Mari exposes an auditable selection portfolio; it does not reproduce model sampling or benchmark metrics.]{.small}
:::


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
