[]{#governed-knowledge}[Supported composition]{.current-label}

# Build governed knowledge

## Flow

From an installed repository checkout:

```{code-block} console
python -m examples.quickstarts.governed_knowledge
```

This composition addresses a CRM revision structurally, resolves a JSON Pointer,
checks the observed value, records the derivation, and commits a reviewable
artifact. The same evidence API accepts text spans, record fields, table cells,
page regions, and media time ranges.

```{literalinclude} ../../../examples/quickstarts/governed_knowledge.py
:language: python
:caption: Typed evidence to a revisioned artifact
```

Page-region and media-range evidence require a caller-supplied locator that can
read the application's chosen PDF, image, audio, or video representation.
Mari validates the reference, visibility set, resolution result, and quoted
material. The application assigns the acceptance policy and transaction.

| Boundary | Returned value |
|---|---|
| Evidence resolution | `LocatedEvidenceReport` with valid rows and individual issues |
| Derived identity | `RevisionRef` containing scope, namespace, object, revision, and optional unit |
| Write | `KnowledgeArtifact` committed with compare-and-swap semantics |
| Adapter verification | `assert_artifact_store_conforms` |

## Maintain derived knowledge

Declare computational inputs with `KnowledgeArtifact.derivation_spec` and the
[dependency planner](dependency-updates.md). Include the selection rule,
implementation version, and configuration as well as source material.
Citation validation checks source resolution. Semantic support and approval
remain separate [governance decisions](../govern/index.md).
