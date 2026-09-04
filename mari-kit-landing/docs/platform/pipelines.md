[]{#pipelines}[Supported]{.current-label}

# Typed knowledge pipelines

## Stage behavior

| Pipeline property | Observable behavior |
|---|---|
| Versioned stage | Configuration contributes to the stage fingerprint |
| Empty output | Valid successful result with an empty batch |
| Stage failure | Dependent stages remain pending |
| Mutation output | Proposal followed by an application policy check and commit |


:::{collapse} Stage trace example

| Stage | Input | Output | Status |
|---|---|---|---|
| `normalize@1` | `" policy "` | `"policy"` | Succeeded, fingerprint recorded |
| `discard-empty@2` | `""` | No output | Succeeded |
| Dependent stage after upstream error | n/a | n/a | Pending |
:::



Composable `Stage` values transform immutable batches. Each run returns outputs
and a complete `StageTrace`. Domain stages emit reviewable artifact
mutations. Storage writes belong to the application.

## How it works

Each stage declares its input and output types. A versioned fingerprint captures
configuration. The stage also states whether it calls an injected service. The
runner orders stages from their dependencies and passes immutable batches. It
records input revisions and stage results. A failure leaves dependent stages
pending. Outputs are mutation proposals. A final policy checks evidence and
scope, then compares the expected artifact revision before the application
commits them.

**Research basis**[Pipeline provenance research](https://arxiv.org/abs/2006.12117){.paper}
ties reproducibility to captured inputs and transformations. Configuration is
part of the record. [Data Cascades](https://doi.org/10.1145/3411764.3445518){.paper}
documents how upstream data failures compound downstream. This motivates stage
identities and dependency traces. Visible failures complete the record. Mari
expresses this boundary through generic stage and mutation types.

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
