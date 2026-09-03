# Ingest & parse

## Choose an ingestion operation


| Input | Operation | Output |
|---|---|---|
| Provider APIs and event notifications | Poll or stream canonical source changes | `SourcePage`, `Document`, `Tombstone`, `ChangeHint` |
| Completed source pages | Reconcile against prior snapshot | Ordered upsert/delete plan and next cursor |
| Documents | Parse and resolve evidence | Typed facts, answers, decisions, summaries, links |
| PDFs, slides, and spreadsheets | Preserve pages, regions, tables, figures, and derived representations | `StructuredDocument` |
| Source repositories | Preserve symbols and structural relations | `CodeSymbol`, `CodeEdge` |
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
structured-documents
code-knowledge
connectors
sync
parsers
sections
tags
```
