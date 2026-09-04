[]{#code-knowledge}[Supported]{.current-label}

# Structured code knowledge

## Behavior

| Evaluation | Reported result | Interpretation |
|---|---:|---|
| Codebase-Memory, 31 repositories | 83% answer quality vs. 92% for file exploration | Structured lookup retains most answer quality |
| Same evaluation | 10x fewer tokens and 2.1x fewer tool calls | Graph lookup can reduce exploratory context |

| Local extraction fixture | Precision | Recall | F1 |
|---|---:|---:|---:|
| Python definitions vs. Tree-sitter | `1.000` | `1.000` | `1.000` |
| TypeScript adapter vs. fixture | `1.000` | `0.667` | `0.800` |

The Python comparison matched four relative symbols and the exact method span.
The TypeScript miss was an interface and arrow-function kind. Extending the kind
vocabulary remains adapter work. Use the extraction scores to choose parser
coverage. Measure token and tool-call figures on your own codebase before using
them for capacity planning.

The results come from the upstream implementation. Mari exposes the
representation needed to reproduce the comparison against lexical and
file-based baselines.

## How it works

Parse a revision into symbols and structural edges. Symbol identity combines
repository, revision, language, qualified name, and source span. Imports,
calls, definitions, inheritance, routes, and references become typed edges.

```{code-block} python
:caption: Represent code structure with a caller-owned language server boundary

from mari_components.documents import CodeEdge, CodeEdgeKind, CodeSymbol, CodeSymbolKind

handler = CodeSymbol(
    symbol_id="src/api.py::refund_order",
    repository="support-api",
    revision="git:41ca2f",
    language="python",
    qualified_name="api.refund_order",
    kind=CodeSymbolKind.FUNCTION,
    start_line=71,
    end_line=104,
)

edge = CodeEdge(
    source_id="src/routes.py::refund",
    target_id=handler.symbol_id,
    kind=CodeEdgeKind.CALLS,
)
```

## Parser definition and options

`parse_python(source, *, repository, revision, path, parser_id=...)` is a
concrete standard-library baseline. It emits a module with nested classes.
Functions and methods become symbols connected by `DEFINES` edges. Local calls
become references. A call edge is emitted when its local name resolves to one
symbol. Other candidate counts remain visible in
`CodeReference.resolved_target_ids`. Same-named module symbols are excluded
from call candidates.

| Output | Important fields |
|---|---|
| `CodeSymbol` | Stable qualified `symbol_id`, revision, path, kind, line span, character span, content revision, parent |
| `CodeReference` | Owning symbol, written name, character span, zero/one/many candidate targets |
| `CodeParseResult` | Symbols, edges, references, positioned issues, parser ID, coordinate unit |

Repeated definitions retain the same qualified name and receive deterministic
`#2`, `#3`, … symbol-ID suffixes. Callers diagnose or reject the duplicate.

```{code-block} python
:caption: Extract Python through the standard-library parser

from mari_components.documents import parse_python

parsed = parse_python(
    source,
    repository="support-api",
    revision=commit_sha,
    path="src/refunds.py",
)

for reference in parsed.references:
    if len(reference.resolved_target_ids) != 1:
        queue_resolution(reference)
```

The built-in parser fails closed with a positioned `syntax_error`. Tree-sitter-
style error recovery belongs in adapters for other languages and partial trees.

Incremental rebuild compares content fingerprints, reparses changed files, removes their prior symbols and edges, and then resolves cross-file references. Impact analysis traverses reverse dependency edges with an explicit depth and edge-kind budget.

## Measures

| Question type | Ground truth |
|---|---|
| Definition lookup | Exact symbol and source span |
| Call-chain tracing | Ordered path of typed edges |
| Change impact | Known affected symbols and files |
| Architecture question | Gold files, blocks, and lines |
| Efficiency | Context tokens and source reads |

::: source-block
**Papers and implementations**

[Codebase-Memory](https://arxiv.org/abs/2603.27277){.paper}[MIT reference implementation](https://github.com/DeusData/codebase-memory-mcp){.paper}[Tree-sitter paper](https://tree-sitter.github.io/tree-sitter/){.paper}[SWE-bench](https://arxiv.org/abs/2310.06770){.paper}

[Mari includes the standard-library Python parser and language-neutral symbols, edges, and impact traversal. Additional language parsers remain integrations.]{.small}
:::
