import ast
import importlib
import inspect
import re
from pathlib import Path

DOCS = Path("mari-kit-landing/docs")
FEATURE_AREAS = (
    "start",
    "ingest",
    "retrieve",
    "govern",
    "memory",
    "graph",
    "agents",
    "platform",
)


def documented_pages() -> list[Path]:
    return [DOCS / "index.md"] + [
        path for area in FEATURE_AREAS for path in sorted((DOCS / area).glob("*.md"))
    ]


def feature_pages() -> list[Path]:
    return [
        path
        for path in documented_pages()
        if path.name not in {"index.md", "maturity.md"}
    ]


def test_reader_documentation_does_not_expose_ci_workflows() -> None:
    markdown = "\n".join(path.read_text() for path in DOCS.rglob("*.md"))
    forbidden = (
        "benchmark first",
        "## reproduce",
        "$ pytest",
        "$ python benchmarks/",
        "not run",
        ".md#evaluation",
    )

    assert not (DOCS / "benchmarks").exists()
    assert [phrase for phrase in forbidden if phrase in markdown.casefold()] == []
    assert not re.search(
        r"(?m)^\s*(?:verified\s+)?\d+\s+(?:tests?\s+)?passed\b", markdown
    )


def prose(markdown: str) -> str:
    value = re.sub(r"```.*?```", "", markdown, flags=re.DOTALL)
    value = re.sub(r"`[^`]+`", "", value)
    return value


def test_pages_open_with_a_direct_section_heading() -> None:
    invalid: list[str] = []
    for path in documented_pages():
        headings = re.findall(r"(?m)^## (.+)$", path.read_text())
        if not headings or any(
            re.match(r"(?:At a glance|Choose |Summary$|Overview$|Why |What )", heading)
            for heading in headings
        ):
            invalid.append(str(path.relative_to(DOCS)))

    assert invalid == []


def test_feature_pages_show_public_api_usage() -> None:
    missing = [
        str(path.relative_to(DOCS))
        for path in feature_pages()
        if "```{code-block} python" not in path.read_text()
        and "```{code-block} console" not in path.read_text()
        and "```{literalinclude}" not in path.read_text()
    ]

    assert missing == []


def test_numeric_comparisons_include_reader_guidance() -> None:
    invalid: list[str] = []
    for path in feature_pages():
        text = path.read_text()
        sections = re.split(r"(?m)^## ", text)
        first_section = sections[1] if len(sections) > 1 else ""
        has_metric = bool(
            re.search(r"\b(?:nDCG|Recall|precision|F1|overlap)\b", first_section)
        )
        table_rows = [
            line for line in first_section.splitlines() if line.startswith("|")
        ]
        has_guidance = any(row.count("|") >= 4 for row in table_rows)
        if has_metric and not has_guidance:
            invalid.append(str(path.relative_to(DOCS)))

    assert invalid == []


def test_documentation_uses_direct_prose() -> None:
    forbidden = re.compile(
        r"—|;|\b(?:genuinely|really|truly|actually)\b"
        r"|\b(?:leverages?|leveraged|leveraging)\b"
        r"|\b(?:underscores?|underscored|underscoring)\b"
        r"|\b(?:reflects?|reflected|reflecting)\b"
        r"|\b(?:not|never|without|rather than|instead of)\b"
        r"|\b(?:whereas|although|however|yet|but|neither|while)\b"
        r"|\b(?:therefore|thus|overall|ultimately|in summary|in short)\b"
        r"|\b(?:the key point|the result is|this shows|this demonstrates|this proves)\b"
        r"|^(?:This page|This section|In this (?:page|section))\b",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    violations = [
        str(path.relative_to(DOCS))
        for path in documented_pages()
        if forbidden.search(prose(path.read_text()))
    ]

    assert violations == []


def python_examples(path: Path) -> list[str]:
    """Read literal Python snippets, excluding MyST directive options."""
    return [
        "\n".join(line for line in body.splitlines() if not line.startswith(":"))
        for body in re.findall(
            r"(?m)^```(?:\{code-block\} python|python)\s*\n(.*?)^```",
            path.read_text(),
            flags=re.DOTALL,
        )
    ]


def test_documented_python_imports_exist() -> None:
    paths = documented_pages() + [
        Path("docs/dependency-updates.md"),
        Path("docs/conversation-knowledge.md"),
    ]
    errors = []
    for path in paths:
        for ordinal, snippet in enumerate(python_examples(path), 1):
            try:
                tree = ast.parse(snippet)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and (
                        node.module or ""
                    ).startswith("mari_components"):
                        module = importlib.import_module(node.module)
                        for name in node.names:
                            if name.name != "*" and not hasattr(module, name.name):
                                errors.append(
                                    f"{path}:{ordinal}: {node.module}.{name.name}"
                                )
            except (SyntaxError, ImportError) as error:
                errors.append(f"{path}:{ordinal}: {error}")
    assert errors == []


def test_architecture_shared_atom_example_runs() -> None:
    for snippet in python_examples(DOCS / "start/architecture.md"):
        exec(compile(snippet, "architecture.md", "exec"), {})


def test_direct_public_api_call_signatures() -> None:
    """Check call shape without executing host callbacks or model services."""
    errors = []
    for path in documented_pages():
        for ordinal, snippet in enumerate(python_examples(path), 1):
            tree = ast.parse(snippet)
            imports = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                    "mari_components"
                ):
                    module = importlib.import_module(node.module)
                    imports.update(
                        (name.asname or name.name, getattr(module, name.name))
                        for name in node.names
                        if name.name != "*"
                    )
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in imports
                ):
                    continue
                if any(isinstance(arg, ast.Starred) for arg in node.args) or any(
                    keyword.arg is None for keyword in node.keywords
                ):
                    continue
                try:
                    inspect.signature(imports[node.func.id]).bind(
                        *[None for _ in node.args],
                        **{keyword.arg: None for keyword in node.keywords},
                    )
                except (TypeError, ValueError) as error:
                    errors.append(f"{path}:{ordinal}: {node.func.id}: {error}")
    assert errors == []


def test_feature_pages_are_in_their_section_navigation() -> None:
    for area in FEATURE_AREAS:
        index = (DOCS / area / "index.md").read_text()
        entries = {
            line.strip()
            for block in re.findall(r"```\{toctree\}(.*?)```", index, re.DOTALL)
            for line in block.splitlines()
            if line.strip() and not line.startswith(":")
        }
        pages = {
            path.stem for path in (DOCS / area).glob("*.md") if path.stem != "index"
        }
        assert pages <= entries, f"{area}: missing navigation entries {pages - entries}"
