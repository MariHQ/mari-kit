# Documentation map

The [reader documentation](../mari-kit-landing/docs/index.md) is organized by
outcome and feature area. Its Sphinx build is published at
[kit.mari.guru](https://kit.mari.guru/). Repository changes require a separate
site build and deployment before they appear there.

## Current integration guides

| Guide | Use it for |
|---|---|
| [Dependency updates](dependency-updates.md) | Shared atom identity, input aspects, completed receipts, and selective rebuilds |
| [Conversation knowledge](conversation-knowledge.md) | Episode extraction, retrieval facets, and current authorized source evidence |
| [Connectors](connectors.md) | Polling, verified event hints, canonical refetch, and sync handoffs |
| [Knowledge parsers](knowledge-parsers.md) | Evidence-validation contracts and task-specific parser behavior |
| [Research algorithms](research-algorithms.md) | Fusion, graph recall, memory reconciliation, and segmentation |
| [Ten paper-derived extensions](ten-paper-extensions.md) | Smaller reusable boundaries from retrieval and memory methods |
| [Contradiction algorithms](contradiction-algorithms.md) | Cross-source retrieval versus within-document validation |
| [Verification algorithms](verification-algorithms.md) | Current candidate selection and separately labeled future directions |

The dependency and conversation guides are included directly in the site.
Other repository notes provide deeper background beside the corresponding
feature pages. Samples with application callbacks are integration sketches.
The [quickstarts](../examples/quickstarts/) contain runnable fixture compositions.

## Design history and validation records

| Note | Status |
|---|---|
| [API foundations](proposed-api-foundations.md) | Original design rationale, with illustrative proposed signatures |
| [Regenold migration proposal](regenold-migration-proposal.md) | Historical recommendations, predating the current retrieval catalog |
| [Reference implementation audit](reference-implementation-audit.md) | Recorded comparisons and license observations, not a current upstream inventory |
| [Contradiction reference validation](contradiction-reference-validation.md) | Pinned comparisons and intentional paper/code differences |
| [Implementation worklog](../IMPLEMENTATION.md) | Completed work and outstanding integration boundaries |

Paper results and small conformance fixtures do not establish production quality
or scaling. Evaluate the host's models, data, authorization, and persistence
together. For docs build and publishing checks, see the
[documentation maintainer guide](../mari-kit-landing/README.md).
