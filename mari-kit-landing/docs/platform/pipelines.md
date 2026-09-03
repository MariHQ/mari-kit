[]{#pipelines}[Current]{.current-label}

# Typed knowledge pipelines

```{include} ../_includes/eval/platform.md
```

Composable `Stage` values transform immutable batches and return outputs plus a complete `StageTrace`. Domain stages may emit reviewable artifact mutations; the runner itself performs no storage writes.

## How it works

Each stage declares input/output types, a versioned configuration fingerprint, and whether it is pure or calls an injected service. The runner topologically orders stages, passes immutable batches, records input revisions and stage results, and stops dependent stages after failure. Outputs are mutation proposals; a final policy validates evidence, scope, and expected artifact revision before the application commits them.

**Research basis**[Pipeline provenance research](https://arxiv.org/abs/2006.12117){.paper} ties reproducibility to captured inputs, transformations, and configuration. [Data Cascades](https://doi.org/10.1145/3411764.3445518){.paper} documents how upstream data failures compound downstream. This motivates stage identities, dependency traces, and visible failures; the generic stage and mutation types are Mari\'s composition boundary.

:::{container} diagram stages
extract*→*resolve*→*link*→*review*→*index
:::

```{code-block} python
:caption: A deterministic pipeline with stage fingerprints and visible failure

from mari_components.platform import Pipeline, Stage

pipeline = Pipeline(
    stages=(
        Stage(
            name="normalize",
            version="1",
            transform=lambda rows: (row.strip() for row in rows),
        ),
        Stage(
            name="discard-empty",
            version="2",
            transform=lambda rows: (row for row in rows if row),
            configuration={"preserve_order": True},
        ),
    )
)

result = pipeline.run([" policy ", ""])
assert result.outputs == ("policy",)
assert result.succeeded
assert result.trace[0].fingerprint
```
