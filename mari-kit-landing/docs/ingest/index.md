# Ingest & parse

## Evaluation

| Feature | Cases | Result | Corpus result |
|---|---:|---:|---|
| [Documents](documents.md#evaluation) | 5 | 5 / 5 pass | Distributed authorization not measured |
| [Polling and streaming connectors](connectors.md#evaluation) | 44 | 44 / 44 pass | Provider throughput not measured |
| [Synchronization](sync.md#evaluation) | 9 | 9 / 9 pass | Recovery throughput not measured |
| [Knowledge parsers](parsers.md#evaluation) | 19 | 19 / 19 pass | Task quality not measured |
| [Sections](sections.md#evaluation) | 3 | 3 / 3 pass | WikiSection not measured |
| [Tags](tags.md#evaluation) | 2 | 2 / 2 pass | Link F1 not measured |

| Input | Operation | Output |
|---|---|---|
| Provider APIs and event notifications | Poll or stream canonical source changes | `SourcePage`, `Document`, `Tombstone`, `ChangeHint` |
| Completed source pages | Reconcile against prior snapshot | Ordered upsert/delete plan and next cursor |
| Documents | Parse and resolve evidence | Typed facts, answers, decisions, summaries, links |
| Markdown bodies | Split and fingerprint | Stable `KnowledgeSection` revisions |

:::{collapse} Worked ingestion flow

| Source event | Connector output | Sync plan | Parser work |
|---|---|---|---|
| New file | Upsert document | Insert stable ID and revision | Parse every section |
| Edited section | Upsert new revision | Replace prior revision | Parse changed section only |
| Deleted file | Tombstone | Delete source document | Invalidate derived artifacts |
:::


```{toctree}
:maxdepth: 1

documents
connectors
sync
parsers
sections
tags
```
