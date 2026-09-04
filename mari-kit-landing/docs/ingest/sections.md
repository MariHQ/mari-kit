[]{#sections}[Supported]{.current-label}

# Sections and incremental fact scans

## Behavior

| Input change | Work selected |
|---|---|
| Unchanged section revision | Skip extraction |
| New or edited section revision | Re-run section-scoped derivations |
| Removed section | Invalidate artifacts that depend on that revision |

For learned topic segmentation, the WikiSection lexical baseline reaches
boundary F1 `0.237`. Treat it as a floor for evaluation.


:::{collapse} Example section change example

| Section | Previous revision | Current revision | Scan |
|---|---|---|---|
| `overview` | `a12` | `a12` | Skip |
| `enterprise-refunds` | `b34` | `c98` | Extract again |
| `exceptions` | n/a | `d77` | Extract |
:::



`document_sections` maps Markdown headings to stable section IDs and content revisions. `section_revisions` builds the current revision map. Fact scans can then skip unchanged sections.

## How it works

Scan Markdown heading lines and classify content before the first heading as a
preamble. Normalize each heading into a slug and suffix collisions
deterministically. Store absolute body offsets and hash each section body into
its revision. `pending_fact_sections` compares `(document_id, section_id) →
revision` with the last committed scan and yields new or changed sections.
Persist scan revisions after extracted facts commit so failed runs remain
retryable.

```{code-block} python
:caption: fact_scan.py

from mari_components.knowledge import (
    document_sections, fact_scan_revisions, pending_fact_sections,
)

sections = document_sections(document)
pending = pending_fact_sections([document], previous_scan_revisions)
facts = [parse_facts([document], model(section.body)) for section in pending]
next_revisions = fact_scan_revisions(pending)  # persist only after facts commit
```

Merge successful scan revisions into durable scan state. The returned map
contains the supplied sections only. Removed sections need a separate
invalidation decision. Parser, prompt, and model changes also need explicit
versioned inputs to the [dependency planner](../start/dependency-updates.md),
since a section scan compares source revisions alone.

## Function definitions and options

| Function | Definition | Options |
|---|---|---|
| `document_sections(document)` | ATX-heading path segmentation with exact body offsets and per-section SHA-256 revisions | Engineering contract. Callers add a tokenizer or model when needed |
| `section_revisions(documents)` | Current `(document_id, section_id) → revision` map | Last duplicate key wins when callers supply duplicate document identities |
| `pending_fact_sections(documents, previous)` | Sections whose current revision differs from committed scan state | Caller owns when the returned work is committed |
| `parse_markdown(...)` | Richer block parser for headings, paragraphs, fenced code and tables | Use when section granularity loses structure |

::: source-block
**Research and standards**

[Build Systems à la Carte: change detection and recomputation](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}[RFC 6920: digest-based content identity](https://www.rfc-editor.org/rfc/rfc6920){.paper}

[Markdown heading segmentation and slug collision rules are Mari engineering contracts.]{.small}
:::
