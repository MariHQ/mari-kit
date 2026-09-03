# Getting started

## Choose a starting point


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
