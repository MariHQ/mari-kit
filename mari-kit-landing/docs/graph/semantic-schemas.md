[]{#semantic-schemas}[Reference]{.current-label}

# Semantic schemas and constraints

## Behavior

| Input | Constraint | Result |
|---|---|---|
| Contract with one customer | Exactly one `customer` relation | Conforms |
| Contract missing an effective date | Required `effective_date` property | Violation at that property |
| `purchased` from Policy to Product | Domain must be Customer | Type violation |

## How it works

`KnowledgeSchema` is an optional validation value alongside Mari's graph model. It describes a small set of concept, property, and relation checks. Validation returns every violation with the focus object and constraint identifier. The caller decides whether that report blocks a write, requests repair, or is ignored.

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
    properties=(PropertyConstraint(
        "Contract", "effective_date", required=True,
        value_type="string", value_format="date",
    ),),
    relations=(RelationConstraint("purchased", source="Customer", target="Product"),),
    allow_unknown_properties=False,
)

report = validate_records(schema, records)
if not report.conforms:
    for violation in report.violations:
        print(violation.focus_id, violation.constraint_id)
```

## Function definitions and options

| Value / function | Options | Meaning |
|---|---|---|
| `PropertyConstraint` | `required`, `minimum_count`, `maximum_count` | Independent cardinality checks |
| `PropertyConstraint` | `value_type` | Empty, string, integer, number, boolean, object, or array |
| `PropertyConstraint` | `value_format` | Empty, ISO date, or timezone-aware ISO date-time. Formats require strings |
| `KnowledgeSchema` | `allow_unknown_properties` | Defaults true for open-world compatibility. False reports undeclared properties |
| `validate_records` | Schema, records, optional relations | Reports duplicate IDs, concepts, properties, types, cardinality, and relation domain/range |

Boolean values fail integer and number constraints, and non-finite floats fail
number constraints. These are explicit scalar checks. Mari leaves values such as
`"14"` unchanged during validation.

Adapters translate this utility to formats such as LinkML and JSON Schema.
SHACL and RDF/OWL adapters can use the same values. SQL DDL or property-graph
constraints need their own mapping. The application controls schema choice,
URI meaning, and its node and edge representation.

## Measures

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
