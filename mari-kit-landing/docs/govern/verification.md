[]{#verification}[Current]{.current-label}

# Verification portfolios

## Contract

| Mechanism | Protects against | Contract boundary |
|---|---|---|
| Best-of-N | A single poor sampled candidate | Correctness when every scorer is wrong |
| Verdict consensus | One unstable judgment | Independence between judges |
| Grounding score | Unsupported required ideas | Truth beyond the supplied evidence |
| Selection trace | Opaque winner choice | Calibration of injected scores |


:::{collapse} Example consensus example

| Candidate | Evidence weight | Verdict |
|---|---:|---|
| A | 0.70 | Supported |
| B | 0.20 | Contradicted |
| C | 0.10 | Uncertain |

The selected verdict is supported. Equal supported and contradicted weight produces abstention, leaving the tie explicit.
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

**Score meaning.** Scores are deterministic quality signals for selection and abstention. Probability calibration belongs to a separate analysis.

## Numerical evidence and conclusion policy

`weighted_mean` returns normalized weights and each observation's numerical
contribution. `wilson_proportion` returns a finite point estimate and interval
for caller-labeled binary outcomes. The caller names outcomes, selects actions, and interprets uncertainty.

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

| Output | What it says | Boundary |
|---|---|---|
| Contribution `0.133` | Observation A's weighted contribution | That A is independent or authoritative |
| Interval containing `0.70` | Sampling uncertainty under a binomial model | Next remediation choice |

[Wilson score interval](https://doi.org/10.1080/01621459.1927.10502953){.paper}[Cochrane statistical methods](https://training.cochrane.org/handbook/current/chapter-10){.paper}

::: source-block
**Research basis**

[Self-consistency improves chain-of-thought reasoning](https://arxiv.org/abs/2203.11171){.paper}[FEVER: evidence-based verification](https://arxiv.org/abs/1803.05355){.paper}[ALCE: citation quality evaluation](https://arxiv.org/abs/2305.14627){.paper}

[Mari exposes an auditable selection portfolio. Model sampling and benchmark metrics belong to the surrounding evaluation system.]{.small}
:::


Verification functions score parsed values and retain successful attempts and failures for audit.

## How it works

`best_of_n` calls the producer up to `n` times and parses each output. Parse
failures remain beside successful siblings. Valid candidates receive scores,
followed by selection with stable first-wins ties. A configured threshold stops
production early. `verdict_consensus` counts typed verdicts. Grounding scores
combine declared deterministic components for ranking or abstention.
Probability calibration requires separate work.

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
