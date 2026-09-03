[]{#living-views}[Current]{.current-label}

# Living knowledge views

## At a glance

| Source change | Dependency relation | View action |
|---|---|---|
| One evidence revision changes | Summary reads that revision | Mark summary stale |
| Entity label changes | Index stores entity text | Rebuild affected index rows |
| Unrelated document changes | No dependency path | Reuse view unchanged |
| Parser version changes | All regions derived by parser | Rebuild matching parser outputs |

## How it works

A view definition fingerprints its transform and configuration. A materialization records exact input revisions and output artifacts. On change, Mari walks the reverse dependency graph and produces the smallest safe rebuild plan. Execution and storage remain caller-owned.

```{code-block} python
:caption: Plan an incremental refresh without hiding dependencies

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

This is dependency-driven recomputation, not autonomous rewriting. Generated summaries remain evidence-bound artifacts and are never treated as source observations.

## What to evaluate

| Measure | Meaning |
|---|---|
| Rebuild precision | Rebuilt artifacts that actually depended on a change |
| Rebuild recall | Changed derivatives that were correctly invalidated |
| Reuse ratio | Safe materializations reused without recomputation |
| Equivalence | Incremental output equals a clean full rebuild |

::: source-block
**Papers and implementations**

[Differential Dataflow](https://www.cidrdb.org/cidr2013/Papers/CIDR13_Paper111.pdf){.paper}[DBSP](https://arxiv.org/abs/2203.16684){.paper}[Self-adjusting computation](https://doi.org/10.1145/1040305.1040311){.paper}[Semiont projections](https://github.com/The-AI-Alliance/semiont){.paper}

[Mari implements invalidation and planning over its existing provenance graph; it does not implement a streaming database engine.]{.small}
:::
