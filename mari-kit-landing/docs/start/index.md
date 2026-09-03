# Getting started

## Evaluation

| Surface | Cases | Result | Detail |
|---|---:|---:|---|
| Installed package | 198 | 198 / 198 pass | [Install](install.md#evaluation) |
| Architecture boundaries | 9 | 9 / 9 pass | [Architecture](architecture.md#evaluation) |

| Page | Covers |
|---|---|
| [Install](install.md) | Base package, optional integrations, injected dependencies |
| [Architecture](architecture.md) | Layer ownership, data flow, framework and storage boundaries |

:::{collapse} Package boundary at a glance

| Supplied by Mari | Injected by the application |
|---|---|
| Types, planning functions, metrics, traces | Models, HTTP clients, databases, authorization, schedulers |
| Reference in-memory algorithms | Production scaling and transaction guarantees |
:::


```{toctree}
:maxdepth: 1

install
architecture
```
