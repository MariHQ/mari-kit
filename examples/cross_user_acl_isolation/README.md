# Cross-user ACL isolation

This example indexes one public incident document and one restricted internal
runbook. An employee and a customer issue the same query:

- The employee's authorized candidate set contains both documents and selects
  the internal runbook and its grounded cached answer.
- The customer's set contains only the public document. Filtering happens
  before MUVERA candidate scoring and exact reranking, and the restricted
  workflow cache is excluded before intent matching.

Mari preserves provider ACL metadata. The host remains responsible for mapping
authenticated users to provider principals and passing the resulting document
IDs to retrieval and cache selection.

```bash
set -a; . examples/cross_user_acl_isolation/.env.example; set +a
python -m examples.cross_user_acl_isolation.main
```
