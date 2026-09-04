[]{#knowledge-portability}[Supported]{.current-label}

# Portable knowledge bundles

## Bundle layout

```text
knowledge.mari/
├── manifest.json
├── records.jsonl
├── provenance.jsonl
├── tombstones.jsonl
└── checksums.sha256
```

| Condition | Library behavior |
|---|---|
| Checksum mismatch | Reject the bundle |
| Unknown format version | Verification reports unsupported format |
| Content ID already present in `existing_ids` | List it in `existing_content_ids` |
| Changed record bytes | Compute a separate content ID |
| Scope outside caller import policy | Application rejects it before applying writes |

## How it works

Canonical JSON encoding produces stable record bytes, and import planning
hashes each record line with SHA-256. The manifest contains format, version,
declared scopes, and checksums for the three data files. Export sorts rows, so
the same inputs produce identical files.

`verify_bundle` checks the format and files named by manifest checksums.
`plan_bundle_import` then partitions record content IDs against `existing_ids`.
Schema validation, logical-identity conflicts, scope enforcement, duplicate-row
handling, and applying records or tombstones belong to the application.

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
# Resolve these IDs against records.jsonl, validate scope/schema, then commit.
print(plan.add_content_ids, plan.existing_content_ids)
```

Signing and encryption are optional adapters. Checksums detect changed bytes.
Signatures can establish publisher identity. Encryption protects bundle
contents in transit or storage.

Treat verification as integrity checking against the supplied manifest. An
untrusted sender can replace both data and checksums. Authenticate the sender
and validate the expected file set, manifest schema, record schemas, and import
policy at the application boundary.

For logs, fixtures, and API boundaries, `to_json_value` recursively converts
Mari dataclasses, enums, immutable mapping proxies, timezone-aware datetimes,
tuples, and sets into JSON-safe values. Unsupported values and naïve datetimes
fail explicitly.

```{code-block} python
:caption: Encode an immutable change hint with the JSON adapter

import json
from mari_components.json import to_json_value

payload = json.dumps(to_json_value(change_hint), sort_keys=True)
```

## Measures

| Invariant | Check |
|---|---|
| Determinism | Same values produce byte-identical files |
| Integrity | A changed data file disagrees with its recorded checksum |
| Round trip | Application import preserves records and provenance |
| Idempotency | Existing record IDs are separated from proposed additions |
| Compatibility | Golden bundles load across supported Mari versions |

::: source-block
**Papers, standards, and implementations**

[Portable Agent Memory](https://arxiv.org/abs/2605.11032){.paper}[Portable Memory reference](https://github.com/MacPaw/portable-memory){.paper}[ApertoMemory](https://github.com/apertomemory/apertomemory){.paper}[RFC 8785 JSON Canonicalization](https://www.rfc-editor.org/rfc/rfc8785){.paper}[Merkle trees](https://doi.org/10.1007/3-540-48184-2_32){.paper}

[Mari currently provides an in-memory bundle value and deterministic codec.
Cross-vendor compatibility
requires a shared profile and independent implementations.]{.small}
:::
