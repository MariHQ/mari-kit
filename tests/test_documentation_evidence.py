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


def test_prompt_language_and_standalone_benchmark_pages_are_absent() -> None:
    markdown = "\n".join(path.read_text() for path in DOCS.rglob("*.md"))

    assert "benchmark first" not in markdown.casefold()
    assert not (DOCS / "benchmarks").exists()
    assert "benchmarks/index" not in (DOCS / "index.md").read_text()


def test_every_documented_feature_page_has_inline_evaluation() -> None:
    missing = [
        str(path.relative_to(DOCS))
        for path in documented_pages()
        if "## Evaluation" not in path.read_text()
    ]

    assert missing == []


def test_every_page_with_a_paper_citation_has_executable_or_linked_evidence() -> None:
    invalid: list[str] = []
    for path in documented_pages():
        text = path.read_text()
        if "{.paper}" not in text:
            continue
        if text.index("## Evaluation") > text.index("{.paper}"):
            invalid.append(str(path.relative_to(DOCS)))
            continue
        evaluation = text.split("## Evaluation", 1)[1]
        if not any(
            marker in evaluation
            for marker in ("$ pytest", "$ python benchmarks/", ".md#evaluation")
        ):
            invalid.append(str(path.relative_to(DOCS)))

    assert invalid == []
