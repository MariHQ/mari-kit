[]{#pipelines}[Supported]{.current-label}

# Typed knowledge pipelines

## Stage behavior

| Pipeline property | Observable behavior |
|---|---|
| Versioned stage | Configuration contributes to the stage fingerprint |
| Empty output | Valid successful result with an empty batch |
| Stage failure | Execution stops and returns the failed stage trace |
| Mutation output | Proposal followed by an application policy check and commit |


:::{collapse} Stage trace example

| Stage | Input | Output | Status |
|---|---|---|---|
| `normalize@1` | `" policy "` | `"policy"` | Succeeded, fingerprint recorded |
| `discard-empty@2` | `""` | No output | Succeeded |
| Later stage after upstream error | n/a | n/a | Skipped, absent from trace |
:::



Composable `Stage` values transform immutable batches. Each run returns outputs
and a `StageTrace` for each attempted stage. Domain stages can emit reviewable artifact
mutations. Storage writes belong to the application.

## How it works

`Pipeline.run` executes stages in their declared tuple order. Each transform
receives a tuple and returns an iterable that becomes the next tuple. Elements
retain their own mutability. Stage fingerprints cover name, version, and
configuration. Bump the version whenever transform behavior changes.

The runner records counts, fingerprints, success, and errors. On an exception,
it returns empty outputs and the trace through the failing stage. Input types,
source revisions, model calls, retries, and commits remain application concerns.
Transforms can return ordinary values or mutation proposals.

For branching dependencies and reusable completed outputs, use the
[shared dependency planner](../start/dependency-updates.md). A pipeline can run
the work for one ready derivation. Persist its successful output and receipt
together through the application's [store boundary](stores.md).

**Research basis**[Pipeline provenance research](https://arxiv.org/abs/2006.12117){.paper}
ties reproducibility to captured inputs and transformations. Configuration is
part of the record. [Data Cascades](https://doi.org/10.1145/3411764.3445518){.paper}
documents how upstream data failures compound downstream. This motivates stage
identities and dependency traces. Visible failures complete the record. Mari
expresses this boundary through generic stage and mutation types.

:::{container} diagram stages
[extract]{.step} [resolve]{.step} [link]{.step} [review]{.step} [index]{.step}
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
