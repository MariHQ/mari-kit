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

A view definition fingerprints its transform and configuration. A materialization records exact input revisions and output artifacts. On change, Mari walks the reverse dependency graph and produces the smallest safe rebuild plan. Execution and storage remain caller-owned.

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
    pipeline.run(task)
```

Dependencies drive recomputation. Generated summaries remain evidence-bound
artifacts. Their provenance marks them as derived values.

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

[Mari implements invalidation and planning over its provenance graph. A
streaming database can execute those plans through an adapter.]{.small}
:::
