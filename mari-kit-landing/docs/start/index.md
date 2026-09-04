# Getting started

## Pages


| Page | Covers |
|---|---|
| [Company search](company-search.md) | A complete authorized retrieval path |
| [Governed knowledge](governed-knowledge.md) | Typed evidence and revisioned artifacts |
| [Agent knowledge](agent-knowledge.md) | Completed activity to reviewable proposals |
| [Conversation knowledge](../agents/conversation-knowledge.md) | Settled conversations to searchable, evidence-bound episodes |
| [Install](install.md) | Base package, optional integrations, injected dependencies |
| [Architecture](architecture.md) | Layer ownership, data flow, framework and storage boundaries |
| [Maturity](maturity.md) | Stability and support labels |
| [Identity migration](identity-migration.md) | Canonical document IDs and configured source fingerprints |
| [Shared dependency updates](dependency-updates.md) | Atom reuse, completed receipts, and change propagation |

:::{collapse} Package boundary

| Supplied by Mari | Injected by the application |
|---|---|
| Types, planning functions, metrics, traces | Models, HTTP clients, databases, authorization, schedulers |
| Reference in-memory algorithms | Production scaling and transaction guarantees |
:::


```{toctree}
:maxdepth: 1

company-search
governed-knowledge
agent-knowledge
install
architecture
maturity
identity-migration
dependency-updates
```
