# Ingest & parse

## Ingestion operations


| Input | Operation | Output |
|---|---|---|
| Provider APIs and event notifications | Poll or stream canonical source changes | `PollPage`, `KnowledgeDocument`, `Tombstone`, `ChangeHint` |
| Completed source pages | Reconcile against prior snapshot | Ordered upsert/delete plan and next cursor |
| Documents | Parse and resolve evidence | Typed facts, answers, decisions, summaries, links |
| PDFs, slides, and spreadsheets | Preserve pages, regions, tables, figures, and derived representations | `StructuredDocument` |
| Source repositories | Preserve symbols and structural relations | `CodeSymbol`, `CodeEdge` |
| Markdown bodies | Split and fingerprint | Stable `KnowledgeSection` revisions |
| Parsed Markdown | Extract stable semantic units | Paragraph, list-item, table-row, code, and fallback atoms |

## Function map

| Function | Required inputs | Principal options | Returns |
|---|---|---|---|
| `parse_markdown` | Text, artifact ID, revision | Table parsing, fence recovery, parser ID | `ParseResult[ParsedDocument]` |
| `parse_html` | Text, artifact ID, revision | Parser ID | Blocks and expanded table cells with raw spans |
| `parse_delimited` | Text, source ID, revision | Delimiter detection, quote character, header, identity fields, strict width | Independently accepted records and positioned issues |
| `parse_json_lines` | Text, source ID, revision | Identity fields, parser ID | Positioned fields. Malformed siblings remain issues |
| `parse_json_array` | JSON array text, source ID, revision | Identity fields, parser ID | Positioned object records and member-specific issues |
| `parse_python` | Source, repository, revision, path | Parser ID | Symbols, definition/call edges, unresolved or ambiguous references |
| `plan_sync` | Prior state, page, source, mode | Full or incremental semantics | Side-effect-free mutations and proposed next state |

:::{collapse} Example ingestion flow

| Source event | Connector output | Sync plan | Parser work |
|---|---|---|---|
| New file | Upsert document | Insert stable ID and revision | Parse every section |
| Edited section | Upsert new revision | Replace prior revision | Parse the changed section |
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
semantic-atoms
tags
```
