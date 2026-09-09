"""Generate the complete public implementation index from Python source ASTs.

Run from any directory. --check verifies that checked-in outputs match source.
Package facades and private helper modules are recorded separately. No optional
runtime dependency or module execution is needed to inspect the source tree.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "mari_kit"
GROUPS = {
    "algorithms": "Selectable algorithm additions",
    "retrieval": "Retrieval and context",
    "documents": "Documents and source structure",
    "knowledge": "Knowledge and memory",
    "graph": "Graph algorithms and interchange",
    "trajectories": "Agent activity and experience",
    "agents": "Agent events and evaluation",
    "governance": "Governance policies",
    "evaluation": "Evaluation and statistics",
    "connectors": "Source connectors and event handling",
    "sync": "Source synchronization",
    "platform": "Platform composition and reference storage",
    "testing": "Conformance utilities",
}
ROOT_GROUPS = {
    "conversation_knowledge": "Conversations and topics",
    "conversation_topics": "Conversations and topics",
    "aggregates": "Incremental maintenance",
    "dependencies": "Incremental maintenance",
    "grouping": "Incremental maintenance",
    "incremental": "Incremental maintenance",
    "selections": "Incremental maintenance",
    "lifecycle": "Retrieval and context",
    "verification": "Verification and evidence decisions",
    "portability": "Platform composition and reference storage",
}


def declaration(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    methods = []
    if isinstance(node, ast.ClassDef):
        methods = [
            {"name": child.name, "line": child.lineno}
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not child.name.startswith("_")
        ]
    return {
        "name": node.name,
        "kind": "class" if isinstance(node, ast.ClassDef) else "function",
        "line": node.lineno,
        "methods": methods,
    }


def generate() -> dict[Path, str]:
    revision = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", "src/mari_kit"],
        cwd=ROOT,
        text=True,
    ).strip()
    modules = []
    facades = []
    private = []
    for path in sorted(SOURCE.rglob("*.py")):
        relative = path.relative_to(SOURCE)
        parts = relative.with_suffix("").parts
        if any(part.startswith("_") and part != "__init__" for part in parts):
            private.append(str(relative))
            continue
        tree = ast.parse(path.read_text())
        name = ".".join(
            ("mari_kit", *(parts[:-1] if parts[-1] == "__init__" else parts))
        )
        definitions = [
            declaration(node)
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        ]
        if not definitions:
            facades.append({"module": name, "path": str(path.relative_to(ROOT))})
            continue
        group = GROUPS.get(
            parts[0], ROOT_GROUPS.get(parts[0], "Shared values and contracts")
        )
        summary = (
            (ast.get_docstring(tree) or "Public implementation definitions.")
            .split("\n\n")[0]
            .replace("\n", " ")
        )
        modules.append(
            {
                "module": name,
                "path": str(path.relative_to(ROOT)),
                "group": group,
                "summary": summary,
                "definitions": definitions,
            }
        )
    count = sum(len(module["definitions"]) for module in modules)
    methods = sum(
        len(definition["methods"])
        for module in modules
        for definition in module["definitions"]
    )
    data = {
        "source_revision": revision,
        "scope": "Public top-level class/function definitions and public methods in all public source modules. Imported aliases, constants, private helpers, and dunder methods are outside the definition count. Pure facades are listed separately.",
        "implementation_modules": len(modules),
        "definitions": count,
        "public_methods": methods,
        "modules": modules,
        "facades": facades,
        "private_modules": private,
    }
    lines = [
        "# Complete module and API index",
        "",
        f"This source-derived index covers **{len(modules)} public implementation modules**, **{count} top-level class/function definitions**, and **{methods} public method declarations**. It includes algorithms, supporting records, protocols, adapters, and validators. These counts describe definitions rather than independent algorithms.",
        "",
        "The [algorithm choices guide](https://kit.mari.guru/start/algorithm-choices.html) compares workloads and tradeoffs. Use this index to locate every public implementation family and inspect exact source definitions. Imported aliases, constants, private helpers, and dunder methods are outside the definition counts. Package facades appear separately below.",
        "",
        f"Source reference: [Mari Kit at {revision[:7]}](https://github.com/MariHQ/mari-kit/tree/{revision}/src/mari_kit). Each declaration links to its implementation. Research citations and adaptation boundaries appear in the algorithm guide and feature pages.",
        "",
        "## Areas",
        "",
    ]
    groups = sorted({module["group"] for module in modules})
    for group in groups:
        anchor = group.lower().replace(" ", "-")
        lines.append(f"- [{group}](#{anchor})")
    for group in groups:
        lines.extend(["", f"## {group}", ""])
        for module in modules:
            if module["group"] != group:
                continue
            url = f"https://github.com/MariHQ/mari-kit/blob/{revision}/{module['path']}"
            lines.extend(
                [
                    f"### {module['module']}",
                    "",
                    module["summary"],
                    "",
                    f"[Module source]({url})",
                    "",
                    "| Public definition | Kind | Public methods declared here |",
                    "|---|---|---|",
                ]
            )
            for definition in module["definitions"]:
                methods_text = (
                    ", ".join(
                        f"[{method['name']}]({url}#L{method['line']})"
                        for method in definition["methods"]
                    )
                    or "—"
                )
                lines.append(
                    f"| [{definition['name']}]({url}#L{definition['line']}) | {definition['kind']} | {methods_text} |"
                )
            lines.append("")
    lines.extend(
        [
            "## Package facades",
            "",
            "These modules expose imports or package metadata. Their implementation definitions are indexed at the owning module above.",
            "",
        ]
    )
    for facade in facades:
        lines.append(
            f"- [{facade['module']}](https://github.com/MariHQ/mari-kit/blob/{revision}/{facade['path']})"
        )
    lines.extend(
        [
            "",
            "## Generation scope",
            "",
            "The index scans every Python source file in `src/mari_kit`, including definitions housed in package initializers. Private modules are excluded from the public index: "
            + ", ".join(f"`{path}`" for path in private)
            + ".",
            "",
            "Maintainers regenerate the Markdown and machine-readable inventory together using `mari-kit-landing/tools/generate_algorithm_inventory.py`. The `--check` option reports stale outputs. Research provenance is maintained in the curated guide instead of inferred from function names.",
            "",
        ]
    )
    return {
        ROOT / "docs/algorithm-inventory.json": json.dumps(data, indent=2) + "\n",
        ROOT / "docs/algorithm-inventory.md": "\n".join(lines),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for path, content in generate().items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(content)
    if stale:
        raise SystemExit("Stale inventory: " + ", ".join(stale))


if __name__ == "__main__":
    main()
