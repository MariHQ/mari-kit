[]{#living-views}[Supported]{.current-label}

# Living knowledge views

## Refresh decisions

| Source change | Dependency relation | View action |
|---|---|---|
| One evidence revision changes | Summary reads that revision | Mark summary stale |
| Entity label changes | Index stores entity text | Rebuild affected index rows |
| Unrelated document changes | No dependency path | Reuse view unchanged |
| Parser version changes | All regions derived by parser | Rebuild matching parser outputs |

## How it works

A `MaterializedView` names a transform version and source pattern. Each
`ViewMaterialization` records its input revisions and output artifact ID.
`plan_view_refresh` compares those records with changed revisions through the
[shared dependency planner](../start/dependency-updates.md). It returns refresh
tasks and reused artifact IDs. Execution and storage remain caller-owned.

```{code-block} python
:caption: Plan an incremental refresh with recorded dependencies

from mari_components.platform import MaterializedView, plan_view_refresh

view = MaterializedView(
    view_id="project-summary",
    transform="summarize-community@2",
    source_pattern="project:mari/**",
)

plan = plan_view_refresh(
    view=view,
    materializations=prior_builds,
    changed_revisions={"github/readme": "git:91df"},
)

for task in plan.tasks:
    rebuild_view(task.artifact_id, reason=task.reason)  # application callback
```

Dependencies drive recomputation. Generated summaries remain evidence-bound
artifacts. Their provenance marks them as derived values.

## Refresh contract

The view adapter accepts revision deltas for existing materializations. It
detects changed inputs, matching source additions, and transform-version
changes. Include configuration changes in the transform identifier. Partition
legacy string source IDs by tenant and space before calling this adapter.

Use `plan_dependency_updates` directly for source deletion, explicit scoped
identities, recipe configuration, and multi-stage graphs. Supply the complete
current source snapshot and derivations. Completed output receipts allow
unchanged output fingerprints to stop downstream work. New view creation and
removal of retired projections are application operations.

## Measures

| Measure | Meaning |
|---|---|
| Rebuild precision | Rebuilt artifacts with a dependency on the change |
| Rebuild recall | Changed derivatives that were correctly invalidated |
| Reuse ratio | Safe materializations reused across the refresh |
| Equivalence | Incremental output equals a clean full rebuild |

::: source-block
**Papers and implementations**

[Differential Dataflow](https://www.cidrdb.org/cidr2013/Papers/CIDR13_Paper111.pdf){.paper}[DBSP](https://arxiv.org/abs/2203.16684){.paper}[Self-adjusting computation](https://doi.org/10.1145/1040305.1040311){.paper}[Semiont projections](https://github.com/The-AI-Alliance/semiont){.paper}

[Mari implements batch dependency comparison and rebuild planning. Streaming
execution and database integration remain application adapters.]{.small}
:::
