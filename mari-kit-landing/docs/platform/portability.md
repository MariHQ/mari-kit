[]{#knowledge-portability}[Current]{.current-label}

# Portable knowledge bundles

## At a glance

```text
knowledge.mari/
├── manifest.json
├── records.jsonl
├── provenance.jsonl
├── tombstones.jsonl
└── checksums.sha256
```

| Validation failure | Import behavior |
|---|---|
| Checksum mismatch | Reject the bundle |
| Unknown required format version | Reject before reading records |
| Duplicate content ID with identical bytes | Idempotent no-op |
| Same logical identity with different content | Preserve both and emit a conflict |
| Scope not importable by caller | Reject that record and report it |

## How it works

Canonical JSON encoding produces a stable SHA-256 content ID for each record. A manifest binds format version, created time, root records, algorithms, schemas, and file checksums. Export order is deterministic, so identical inputs produce identical logical contents. Import validates the complete bundle before proposing any writes.

```{code-block} python
:caption: Export, verify, and plan a portable import

from mari_components.portability import export_bundle, plan_bundle_import, verify_bundle

bundle = export_bundle(
    records=records,
    provenance=provenance,
    tombstones=tombstones,
    scopes=("project:mari",),
)

report = verify_bundle(bundle)
assert report.valid

plan = plan_bundle_import(bundle, existing_ids=store.content_ids())
store.apply(plan)  # application-owned transaction
```

Signing and encryption are optional adapters. Checksums provide integrity, not identity or secrecy.

## What to evaluate

| Invariant | Check |
|---|---|
| Determinism | Same values produce byte-identical files |
| Tamper detection | Every changed byte invalidates its checksum |
| Round trip | Export-import preserves records and provenance |
| Idempotency | Re-import creates no duplicate records |
| Compatibility | Golden bundles load across supported Mari versions |

::: source-block
**Papers, standards, and implementations**

[Portable Agent Memory](https://arxiv.org/abs/2605.11032){.paper}[Portable Memory reference](https://github.com/MacPaw/portable-memory){.paper}[ApertoMemory](https://github.com/apertomemory/apertomemory){.paper}[RFC 8785 JSON Canonicalization](https://www.rfc-editor.org/rfc/rfc8785){.paper}[Merkle trees](https://doi.org/10.1007/3-540-48184-2_32){.paper}

[Both checked-out references are MIT licensed. Mari's first pass is an in-memory bundle value and deterministic codec, not a cross-vendor standard claim.]{.small}
:::
