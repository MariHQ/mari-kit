from mari_components.retrieval import (
    ContextBudget,
    ContextCandidate,
    ContextExclusion,
    assemble_context,
)


def candidate(
    identifier: str,
    *,
    score: float,
    tokens: int = 3,
    authorized: bool = True,
    fresh: bool = True,
) -> ContextCandidate:
    return ContextCandidate(
        document_id=identifier,
        revision="v1",
        text=f"text {identifier}",
        token_count=tokens,
        score=score,
        authorized=authorized,
        fresh=fresh,
    )


def test_context_filters_and_packs_whole_excerpts_with_trace() -> None:
    result = assemble_context(
        [
            candidate("secret", score=10, authorized=False),
            candidate("stale", score=9, fresh=False),
            candidate("a", score=2, tokens=4),
            candidate("b", score=1, tokens=4),
        ],
        budget=ContextBudget(tokens=5, documents=2),
    )

    assert result.document_ids == ("a",)
    assert result.token_count == 4
    reasons = {row.document_id: row.reason for row in result.trace}
    assert reasons == {
        "secret": ContextExclusion.UNAUTHORIZED,
        "stale": ContextExclusion.STALE,
        "a": None,
        "b": ContextExclusion.TOKEN_LIMIT,
    }
