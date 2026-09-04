# Maturity labels

## Labels

Mari separates API availability from support maturity.

| Label | Meaning |
|---|---|
| Core | Cross-system contract whose compatibility is protected |
| Supported | Intended for application use with documented behavior |
| Reference | Local correctness-oriented implementation used for conformance and evaluation |
| Experimental | Importable API whose shape or semantics may change |
| Research | Paper-derived implementation used to study a method |
| Proposed | Documented design awaiting a supported implementation |

Reference and research implementations expose the same inputs, outputs, and
measurements that production adapters need. Their label makes no claim about
distributed capacity, latency, or operational suitability.
