[]{#graph-interoperability}[Current]{.current-label}

# Graph interchange helpers

## Behavior

| Target | Preserved directly | Reported as potential loss |
|---|---|---|
| NetworkX | Node IDs, attributes, edge endpoints and attributes | Backend-specific indexes and transactions |
| GraphML | Scalar attributes and directedness | Nested values, arbitrary Python objects, hyperedges |
| JSON-LD | IDs, types, predicates, JSON literals | Property-graph edge identity unless explicitly reified |
| RDFLib | RDF terms and triples | Reification for parallel identical property edges |
| PyTorch Geometric | Indexed edge tensor | Untensorized application attributes unless mapped by caller |

## How it works

Mari uses a transient `GraphProjection` at the conversion boundary. Application records remain the canonical model. Export functions return bytes or ordinary mappings together with `InterchangeReport`, which lists skipped fields and lossy conversions.

```{code-block} python
:caption: Export a temporary projection and inspect losses

from mari_components.graph import GraphProjection, ProjectionEdge, to_graphml

projection = GraphProjection(
    nodes=(("customer:42", {"kind": "Customer"}),),
    edges=(ProjectionEdge("customer:42", "product:7", "purchased"),),
    directed=True,
)

encoded = to_graphml(projection)
if encoded.report.losses:
    logger.warning("GraphML conversion losses: %s", encoded.report.losses)
write_bytes(encoded.data)
```

## Measures

| Invariant | Check |
|---|---|
| Determinism | Same projection produces identical bytes |
| Escaping | IDs and attributes containing XML/JSON metacharacters round-trip |
| Loss visibility | Unsupported nested values produce report entries |
| Optional dependency | NetworkX and RDFLib load when their adapters are used |

::: source-block
**Standards and implementations**

[GraphML specification](http://graphml.graphdrawing.org/specification.html){.paper}[JSON-LD 1.1](https://www.w3.org/TR/json-ld11/){.paper}[RDF 1.1 concepts](https://www.w3.org/TR/rdf11-concepts/){.paper}[NetworkX](https://github.com/networkx/networkx){.paper}

[Interop carriers exist for conversion. Application records remain the source of truth.]{.small}
:::
