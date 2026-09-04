from __future__ import annotations

import datetime as dt
import itertools

import pytest

from mari_components.documents import (
    AtomDiffAlgorithm,
    AtomKind,
    DiffKind,
    TemporalAtom,
    active_atoms,
    align_atoms,
    content_defined_spans,
    myers_diff,
    parse_markdown,
    patience_diff,
    plan_atom_refresh,
    semantic_atoms,
)
from mari_components.retrieval import (
    AtomVectorHit,
    MultiVectorSection,
    aggregate_atom_hits,
    assemble_atom_context,
    maxsim_section_score,
)

OLD = """# Pricing

Standard plans are billed monthly.

## Enterprise

Enterprise plans start at $499/month.

Plans include SSO and audit logs.

- Annual contracts receive a 15% discount.
- Contact sales for more than 500 seats.
"""

NEW = """# Pricing

New customers receive a guided setup.

Standard plans are billed monthly.

## Enterprise

Enterprise plans start at $599/month.

Plans include SSO and audit logs.

- Annual contracts receive a 15% discount.
- Contact sales for more than 500 seats.
"""


def _atoms(text: str, revision: str):
    parsed = parse_markdown(text, artifact_id="pricing", revision=revision)
    return semantic_atoms(parsed.values[0])


@pytest.mark.parametrize("algorithm", [myers_diff, patience_diff])
def test_sequence_diffs_align_insert_and_replace(algorithm) -> None:
    spans = algorithm(("A", "B", "C", "D", "E"), ("A", "X", "B", "C'", "D", "E"))
    assert [span.kind for span in spans] == [
        DiffKind.EQUAL,
        DiffKind.INSERT,
        DiffKind.EQUAL,
        DiffKind.REPLACE,
        DiffKind.EQUAL,
    ]
    assert spans[1].new_start == 1
    assert spans[3].old_start == 2


@pytest.mark.parametrize("algorithm", [myers_diff, patience_diff])
def test_sequence_diffs_reconstruct_every_short_binary_sequence(algorithm) -> None:
    values = ("A", "B")
    sequences = [
        value
        for length in range(5)
        for value in itertools.product(values, repeat=length)
    ]
    for old in sequences:
        for new in sequences:
            rebuilt: list[str] = []
            for span in algorithm(old, new):
                if span.kind in {DiffKind.EQUAL, DiffKind.INSERT, DiffKind.REPLACE}:
                    rebuilt.extend(new[span.new_start : span.new_end])
            assert tuple(rebuilt) == new


def test_myers_finds_the_minimum_insert_delete_cost() -> None:
    values = ("A", "B")
    sequences = [
        value
        for length in range(5)
        for value in itertools.product(values, repeat=length)
    ]
    for old in sequences:
        for new in sequences:
            spans = myers_diff(old, new)
            observed = sum(
                (span.old_end - span.old_start) + (span.new_end - span.new_start)
                for span in spans
                if span.kind is not DiffKind.EQUAL
            )
            expected = _insert_delete_distance(old, new)
            assert observed == expected


def test_semantic_atoms_keep_identity_when_an_earlier_paragraph_is_inserted() -> None:
    old, new = _atoms(OLD, "old"), _atoms(NEW, "new")
    old_by_text = {atom.text: atom for atom in old}
    new_by_text = {atom.text: atom for atom in new}
    stable_text = "Plans include SSO and audit logs."
    assert old_by_text[stable_text].atom_id == new_by_text[stable_text].atom_id
    assert (
        new_by_text["Annual contracts receive a 15% discount."].kind
        is AtomKind.LIST_ITEM
    )
    assert new_by_text[stable_text].heading_path == ("Pricing", "Enterprise")
    assert (
        NEW[new_by_text[stable_text].start : new_by_text[stable_text].end]
        == stable_text
    )

    alignment = align_atoms(old, new, algorithm=AtomDiffAlgorithm.PATIENCE)
    assert len(alignment.inserted) == 1
    assert len(alignment.modified) == 1
    assert alignment.modified[0].before.text.endswith("$499/month.")
    assert alignment.modified[0].after.text.endswith("$599/month.")
    plan = plan_atom_refresh(alignment)
    assert len(plan.embed_atom_ids) == 2
    assert len(plan.reuse_embeddings) == len(old) - 1
    assert plan.invalidate_section_ids == ("pricing", "pricing/enterprise")
    assert not plan.rebuild_parent_embeddings_eagerly


def test_heading_move_reuses_raw_vector_but_rebuilds_contextual_vector() -> None:
    before = _atoms("# Pricing\n\nPlans include SSO.\n", "before")
    after = _atoms("# Enterprise\n\nPlans include SSO.\n", "after")
    alignment = align_atoms(before, after)
    plan = plan_atom_refresh(alignment)

    assert plan.reuse_raw_embeddings == ((before[0].atom_id, after[0].atom_id),)
    assert plan.reuse_contextual_embeddings == ()
    assert plan.embed_raw_atom_ids == ()
    assert plan.embed_contextual_atom_ids == (after[0].atom_id,)
    assert plan.tombstone_atom_ids == (before[0].atom_id,)
    assert plan.invalidate_section_ids == ("enterprise", "pricing")
    assert plan.invalidate_page_embedding


def test_content_defined_fallback_is_stable_before_an_appended_suffix() -> None:
    original = "word " * 1_000
    before = content_defined_spans(
        original, minimum_characters=128, average_characters=256, maximum_characters=512
    )
    after = content_defined_spans(
        original + ("extra " * 100),
        minimum_characters=128,
        average_characters=256,
        maximum_characters=512,
    )
    assert before[:-1] == after[: len(before) - 1]


def test_parent_aggregation_uses_top_atoms_without_large_section_penalty() -> None:
    hits = (
        AtomVectorHit(
            atom_id="price", source_id="pricing", section_id="enterprise", score=0.92
        ),
        AtomVectorHit(
            atom_id="sales", source_id="pricing", section_id="enterprise", score=0.87
        ),
        AtomVectorHit(
            atom_id="billing", source_id="billing", section_id="enterprise", score=0.81
        ),
        AtomVectorHit(
            atom_id="weak", source_id="billing", section_id="enterprise", score=0.10
        ),
    )
    ranked = aggregate_atom_hits(hits, weights=(1.0, 0.4, 0.2))
    assert ranked[0].parent_id == "pricing#enterprise"
    assert ranked[0].score == pytest.approx(0.92 + 0.4 * 0.87)


def test_multi_query_maxsim_and_retrieval_time_neighbor_expansion() -> None:
    section = MultiVectorSection(
        section_id="enterprise",
        source_id="pricing",
        title_vector=None,
        section_vector=None,
        atom_vectors={"price": (1.0, 0.0), "sso": (0.0, 1.0)},
        contextual_atom_vectors={"price": (1.0, 0.0), "sso": (0.0, 1.0)},
    )
    assert maxsim_section_score([(1.0, 0.0), (0.0, 1.0)], section) == pytest.approx(1.0)
    weighted = MultiVectorSection(
        section_id="weighted",
        source_id="pricing",
        title_vector=None,
        section_vector=None,
        atom_vectors={"only-first": (1.0, 0.0)},
        contextual_atom_vectors={"only-first": (1.0, 0.0)},
    )
    assert maxsim_section_score(
        [(1.0, 0.0), (0.0, 1.0)], weighted, query_weights=(3.0, 1.0)
    ) == pytest.approx(0.75)

    atoms = _atoms(OLD, "r1")
    hit = next(atom for atom in atoms if atom.text.startswith("Plans include SSO"))
    counts = {atom.atom_id: 10 for atom in atoms}
    context = assemble_atom_context(
        atoms,
        hit_atom_ids=[hit.atom_id],
        token_counts=counts,
        token_budget=30,
        neighbors=2,
    )
    assert hit.atom_id in context.selected_atom_ids
    assert context.token_count == 30
    assert context.chunks[0].hit_atom_ids == (hit.atom_id,)

    separated = assemble_atom_context(
        atoms,
        hit_atom_ids=[atoms[0].atom_id, atoms[-1].atom_id],
        token_counts=counts,
        token_budget=20,
        neighbors=0,
    )
    assert len(separated.chunks) == 2


def test_temporal_atoms_answer_current_and_historical_queries() -> None:
    old, new = _atoms(OLD, "old"), _atoms(NEW, "new")
    old_price = next(atom for atom in old if "$499" in atom.text)
    new_price = next(atom for atom in new if "$599" in atom.text)
    utc = dt.UTC
    changed = dt.datetime(2026, 3, 14, tzinfo=utc)
    versions = (
        TemporalAtom(
            atom=old_price,
            valid_from=dt.datetime(2026, 1, 1, tzinfo=utc),
            valid_to=changed,
            recorded_at=dt.datetime(2026, 1, 1, tzinfo=utc),
            embedding_model="embed-v1",
            embedding_version="1",
        ),
        TemporalAtom(
            atom=new_price,
            valid_from=changed,
            recorded_at=changed,
            embedding_model="embed-v1",
            embedding_version="1",
        ),
    )
    february = active_atoms(
        versions,
        at=dt.datetime(2026, 2, 1, tzinfo=utc),
        known_at=dt.datetime(2026, 4, 1, tzinfo=utc),
    )
    april = active_atoms(
        versions,
        at=dt.datetime(2026, 4, 1, tzinfo=utc),
        known_at=dt.datetime(2026, 4, 1, tzinfo=utc),
    )
    assert "$499" in february[0].atom.text
    assert "$599" in april[0].atom.text


def _insert_delete_distance(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            if left_value == right_value:
                current.append(previous[right_index - 1])
            else:
                current.append(min(previous[right_index], current[-1]) + 1)
        previous = current
    return previous[-1]
