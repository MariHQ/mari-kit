[]{#documents}[Current]{.current-label}

# Documents, identity, and ACLs

`KnowledgeDocument` is the canonical provider-owned record. Its stable ID is `{source_id}/{external_id}`. Domain values are frozen dataclasses.

## How it works

`source_id` names one configured source; `external_id` is the provider's stable object key. Their pair prevents two providers from colliding. `revision` identifies content version, while `updated_at` is descriptive metadata and is never used as identity. ACL visibility and principals travel with the document so an allowed-ID set can be computed before retrieval scoring. Frozen values prevent an indexed object from changing behind its recorded revision.

```{code-block} python
:caption: document.py

from mari_components import DocumentACL, KnowledgeDocument, Principal

doc = KnowledgeDocument(
    source_id="github:acme/product",
    external_id="file:docs/refunds.md",
    title="Refund policy",
    body="## Enterprise\nRefunds close after 30 days.",
    revision="8f31c2a", updated_at="2026-08-31T10:00:00Z",
    source_url="https://github.com/acme/product/blob/main/docs/refunds.md",
    acl=DocumentACL(visibility="restricted", principals=(
        Principal(kind="team", identifier="support"),
    )),
    metadata={"path": "docs/refunds.md"},
)
assert doc.document_id == "github:acme/product/file:docs/refunds.md"
```

::::::: cards
::: card
`PollPage`

Upserts, tombstones, cursor, checkpoint, snapshot completeness, provider metadata.
:::

::: card
`Tombstone`

Explicit deletion by source and external ID.
:::

::: card
`KnowledgeSection`

Stable section ID, offsets, text, and section revision.
:::

::: card
`Evidence`

Exact quote plus document, revision, span, and optional section coordinates.
:::
:::::::

::: source-block
**Research and standards**

[W3C PROV: entity identity and revision](https://www.w3.org/TR/prov-dm/){.paper}[Zanzibar: relationship-based authorization](https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/){.paper}

[Mari carries principals and visibility but does not implement an authorization engine. The application resolves those fields to `allowed_document_ids`.]{.small}
:::
