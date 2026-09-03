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
    return [path for path in documented_pages() if path.name != "index.md"]


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
    assert not re.search(r"(?m)^\s*(?:verified\s+)?\d+\s+(?:tests?\s+)?passed\b", markdown)


def test_pages_open_with_an_orientation_section() -> None:
    invalid: list[str] = []
    for path in documented_pages():
        first_h2 = re.search(r"(?m)^## (.+)$", path.read_text())
        if first_h2 is None or not (
            first_h2.group(1) == "At a glance"
            or first_h2.group(1).startswith("Choose ")
        ):
            invalid.append(str(path.relative_to(DOCS)))

    assert invalid == []


def test_feature_pages_show_public_api_usage() -> None:
    missing = [
        str(path.relative_to(DOCS))
        for path in feature_pages()
        if "```{code-block} python" not in path.read_text()
        and "```{code-block} console" not in path.read_text()
    ]

    assert missing == []


def test_numeric_comparisons_include_reader_guidance() -> None:
    invalid: list[str] = []
    for path in feature_pages():
        text = path.read_text()
        sections = re.split(r"(?m)^## ", text)
        first_section = sections[1] if len(sections) > 1 else ""
        has_metric = bool(re.search(r"\b(?:nDCG|Recall|precision|F1|overlap)\b", first_section))
        has_guidance = any(
            phrase in first_section.casefold()
            for phrase in (
                "guidance",
                "use ",
                "choose ",
                "appropriate",
                "does not",
                "trade-off",
                "infer",
                "application-owned",
                "implication",
                "helps",
            )
        )
        if has_metric and not has_guidance:
            invalid.append(str(path.relative_to(DOCS)))

    assert invalid == []
