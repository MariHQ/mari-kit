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
