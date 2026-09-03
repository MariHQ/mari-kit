[]{#sections}[Current]{.current-label}

# Sections and incremental fact scans

## At a glance

| Input change | Work selected |
|---|---|
| Unchanged section revision | Skip extraction |
| New or edited section revision | Re-run section-scoped derivations |
| Removed section | Invalidate artifacts that depend on that revision |

For learned topic segmentation, the WikiSection lexical baseline reaches boundary F1 `0.237`; use it as a floor, not as evidence that lexical boundaries are adequate.


:::{collapse} Worked section change example

| Section | Previous revision | Current revision | Scan |
|---|---|---|---|
| `overview` | `a12` | `a12` | Skip |
| `enterprise-refunds` | `b34` | `c98` | Extract again |
| `exceptions` | — | `d77` | Extract |
:::



`document_sections` maps Markdown headings to stable section IDs and content revisions. `section_revisions` builds the current revision map. Fact scans can then skip unchanged sections.

## How it works

Scan Markdown heading lines, treating content before the first heading as a preamble. Normalize each heading into a slug and suffix collisions deterministically. Store absolute body offsets and hash the section body into its revision. `pending_fact_sections` compares `(document_id, section_id) → revision` with the last committed scan and yields new or changed sections only. Persist new scan revisions only after extracted facts commit, or a failed run would incorrectly suppress retry.

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

::: source-block
**Research and standards**

[Build Systems à la Carte: change detection and recomputation](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}[RFC 6920: digest-based content identity](https://www.rfc-editor.org/rfc/rfc6920){.paper}

[Markdown heading segmentation and slug collision rules are Mari engineering contracts.]{.small}
:::
