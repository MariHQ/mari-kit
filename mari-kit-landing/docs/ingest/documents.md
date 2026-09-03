[]{#documents}[Current]{.current-label}

# Documents, identity, and ACLs

## Behavior

| Concern | Representation |
|---|---|
| Source identity | Stable `(source, external_id)` independent of content |
| Content identity | Revision digest for the exact evidence-bearing body |
| Visibility | Tenant, principal, and group ACL carried with the document |
| Deletion | Explicit tombstone for a removed source object |


:::{collapse} Example document revision example

| Field | Revision A | Revision B |
|---|---|---|
| Stable ID | `github:acme/docs/refunds.md` | `github:acme/docs/refunds.md` |
| Revision | `sha256:8f31` | `sha256:b714` |
| Visibility | `support` | `support` |
| Body | Original policy | Updated policy |

The stable ID identifies the source object. The revision identifies the exact evidence-bearing content.
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

[Mari carries principals and visibility. The application resolves those fields to `allowed_document_ids`. Authorization remains an application concern.]{.small}
:::


`KnowledgeDocument` is the canonical provider-owned record. Its stable ID is `{source_id}/{external_id}`. Domain values are frozen dataclasses.

## How it works

`source_id` names one configured source. `external_id` is the provider's stable object key. Their pair keeps provider identities distinct. `revision` identifies content version. `updated_at` is descriptive metadata. ACL visibility and principals travel with the document so an allowed-ID set can be computed before retrieval scoring. Frozen values keep an indexed object aligned with its recorded revision.

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

## Definitions and options

| Value or function | Definition | Options that change behavior |
|---|---|---|
| `KnowledgeDocument` | Stable `source_id` + `external_id`, immutable `revision`, body and observed ACL | `updated_at`, URL, metadata and principals are descriptive |
| `ParsedBlock` | Parser-neutral kind, text, parent, raw character span and optional table cells | `metadata` retains format-specific facts beside the core type |
| `ParseResult[T]` | Accepted values plus positioned warning/error issues and parser provenance | `source_revision` and parser-specific metadata |
| `stable_source_id(parts, prefix, digest_bytes)` | Type-tags and length-prefixes caller-selected components before SHA-256 hashing | Digest size is 8–32 bytes. Mapping/set order is canonicalized. Identity fields come from the caller |
| `SourceCoordinateMap.build(text, encoding)` | Maps character boundaries to encoded byte boundaries exactly | `to_character(..., exact=False)` floors a mid-character byte offset |

The coordinate map uses the codec's incremental encoder, so BOM and stateful
encodings are counted once. For UTF-16, `byte_length` equals the complete
encoded source length, with one BOM for the complete source.

```{code-block} python
:caption: Preserve parser provenance and explicit coordinate units

from mari_components.documents import SourceCoordinateMap, stable_source_id

record_id = stable_source_id(
    (source_id, row["policy_id"], row["jurisdiction"]),
    prefix="record",
)
coordinates = SourceCoordinateMap.build(source_text, encoding="utf-8")
character_span = coordinates.byte_span_to_characters(node.start_byte, node.end_byte)
```

::::::: cards
::: card
`PollPage`

Upserts, tombstones, cursor, checkpoint, snapshot completeness, provider metadata.
:::
