[]{#semantic-schemas}[Current]{.current-label}

# Semantic schemas and constraints

## At a glance

| Input | Constraint | Result |
|---|---|---|
| Contract with one customer | Exactly one `customer` relation | Conforms |
| Contract without effective date | Required `effective_date` property | Violation at that property |
| `purchased` from Policy to Product | Domain must be Customer | Type violation |

## How it works

`KnowledgeSchema` is an optional validation value, not Mari's graph model. It describes a small set of concept, property, and relation checks. Validation returns every violation with the focus object and constraint identifier; the caller decides whether that report blocks a write, requests repair, or is ignored.

```{code-block} python
:caption: Define a backend-neutral semantic contract

from mari_components.schema import (
    ConceptType,
    KnowledgeSchema,
    PropertyConstraint,
    RelationConstraint,
    validate_records,
)

schema = KnowledgeSchema(
    schema_id="commerce",
    version="2",
    concepts=(ConceptType("Customer"), ConceptType("Contract"), ConceptType("Product")),
    properties=(PropertyConstraint("Contract", "effective_date", required=True),),
    relations=(RelationConstraint("purchased", source="Customer", target="Product"),),
)

report = validate_records(schema, records)
if not report.conforms:
    for violation in report.violations:
        print(violation.focus_id, violation.constraint_id)
```

Adapters may translate this utility to LinkML, JSON Schema, SHACL, RDF/OWL, SQL DDL, or property-graph constraints. Core Mari does not require a schema, RDF, globally meaningful URIs, or a particular node and edge representation.

## What to evaluate

| Layer | Measure |
|---|---|
| Constraint engine | Conformance against hand-labeled valid and invalid records |
| Adapter | Round-trip preservation of required/cardinality/domain/range semantics |
| Migration | Violations introduced and records requiring transformation |
| Extraction | Schema-valid precision and recall of proposed entities/relations |

::: source-block
**Papers, standards, and implementations**

[SHACL Recommendation](https://www.w3.org/TR/shacl/){.paper}[OWL 2 overview](https://www.w3.org/TR/owl2-overview/){.paper}[LinkML](https://github.com/linkml/linkml){.paper}[pySHACL](https://github.com/RDFLib/pySHACL){.paper}[Shape Expressions](https://doi.org/10.1007/978-3-319-68204-4_4){.paper}

[LinkML and pySHACL are Apache-2.0 references. Mari implements a small common constraint kernel and leaves standards-complete validation to adapters.]{.small}
:::
