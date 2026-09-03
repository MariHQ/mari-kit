from __future__ import annotations

import datetime as dt

import pytest

from mari_components.graph import (
    FieldAgreement,
    ResolutionDecision,
    TemporalFact,
    close_transaction,
    query_temporal_facts,
    resolve_entity,
)

UTC = dt.UTC


def test_bitemporal_query_separates_truth_from_system_knowledge() -> None:
    fact = TemporalFact(
        fact_id="employment:v1",
        subject="sam",
        predicate="works_at",
        object="A",
        valid_from=dt.datetime(2025, 1, 1, tzinfo=UTC),
        valid_to=dt.datetime(2025, 7, 1, tzinfo=UTC),
        recorded_at=dt.datetime(2025, 8, 1, tzinfo=UTC),
    )
    closed = close_transaction(fact, retracted_at=dt.datetime(2025, 9, 1, tzinfo=UTC))

    assert query_temporal_facts(
        [closed],
        at=dt.datetime(2025, 6, 1, tzinfo=UTC),
        known_at=dt.datetime(2025, 8, 15, tzinfo=UTC),
    ) == (closed,)
    assert (
        query_temporal_facts(
            [closed],
            at=dt.datetime(2025, 6, 1, tzinfo=UTC),
            known_at=dt.datetime(2025, 9, 2, tzinfo=UTC),
        )
        == ()
    )


def test_bitemporal_intervals_are_half_open_and_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TemporalFact(
            fact_id="x",
            subject="s",
            predicate="p",
            object="o",
            valid_from=dt.datetime(2025, 1, 1),
            recorded_at=dt.datetime.now(UTC),
        )


def test_fellegi_sunter_resolution_exposes_contributions() -> None:
    result = resolve_entity(
        [
            FieldAgreement(
                field="email",
                agrees=True,
                match_probability=0.99,
                nonmatch_probability=0.01,
            ),
            FieldAgreement(
                field="name",
                agrees=False,
                match_probability=0.9,
                nonmatch_probability=0.2,
            ),
        ],
        link_threshold=2.0,
        review_threshold=0.0,
    )

    assert result.decision is ResolutionDecision.LINK
    assert dict(result.contributions)["email"] > 0
    assert dict(result.contributions)["name"] < 0
