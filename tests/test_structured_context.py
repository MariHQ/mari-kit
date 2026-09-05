import random
from dataclasses import replace

import pytest

from mari_components.documents import parse_markdown, semantic_atoms
from mari_components.references import LocatedEvidence, ObjectRef, RevisionRef, TextSpan
from mari_components.retrieval import (
    ContextExpansionPolicy,
    ContextHit,
    StructuredContextItem,
    context_items_from_atoms,
    expand_structured_context,
)


def item(index, text, section="s", label="text", revision="r1"):
    return StructuredContextItem(
        evidence=LocatedEvidence(
            ref=RevisionRef(
                object=ObjectRef(namespace="docs", object_id="doc"),
                revision=revision,
                unit_id=str(index),
            ),
            locator=TextSpan(start=100, end=100 + len(text)),
            quote=text,
        ),
        ordinal=index,
        section_id=section,
        label=label,
        page_numbers=(index + 1,),
    )


def expand(items, indices, budget, **kwargs):
    hits = [
        ContextHit(ref=items[index].evidence.ref, score=float(index))
        for index in indices
    ]
    return expand_structured_context(
        items,
        hits,
        policy=ContextExpansionPolicy(max_chars=budget, **kwargs),
        allowed_refs=[i.evidence.ref for i in items],
    )


def test_entire_section_and_tight_figures_and_noise_policy():
    items = [
        item(0, "long unrelated introduction"),
        item(1, "figure", "figure", "picture"),
        item(2, "footer", "figure", "page_footer"),
        item(3, "unrelated section", "next"),
    ]
    result = expand(items, [1], 100, excluded_labels=frozenset({"page_footer"}))
    assert result.windows[0].text == "figure"
    assert result.windows[0].page_numbers == (2,)
    # Noise is caller-selected, and directly retrieved evidence is never hidden.
    result = expand(items, [2], 6, excluded_labels=frozenset({"page_footer"}))
    assert result.windows[0].text == "footer"


def test_small_prose_sections_grow_across_boundaries_but_large_sections_stay_bounded():
    items = [item(0, "before", "a"), item(1, "tiny", "b"), item(2, "after", "c")]
    assert expand(items, [1], 100).windows[0].text == "before\n\ntiny\n\nafter"
    assert expand(items, [1], 10).windows[0].text == "tiny"
    large = [
        item(0, "unrelated", "a"),
        item(1, "x" * 100, "b"),
        item(2, "neighbor", "b"),
        item(3, "unrelated", "c"),
    ]
    assert all(
        fragment.evidence.ref.unit_id in {"1", "2"}
        for fragment in expand(large, [1], 20).windows[0].fragments
    )


def test_overlap_merge_keeps_every_anchor_and_best_scoring_identity():
    items = [item(0, "alpha"), item(1, "middle"), item(2, "omega")]
    result = expand(items, [0, 2], 30)
    assert len(result.windows) == 1
    assert result.windows[0].primary_ref == items[2].evidence.ref
    assert set(result.windows[0].matched_refs) == {
        items[0].evidence.ref,
        items[2].evidence.ref,
    }
    split = expand(items, [0, 2], 10)
    assert len(split.windows) == 2
    assert any("alpha" in window.text for window in split.windows)
    assert any("omega" in window.text for window in split.windows)
    adjacent = [item(0, "first section", "a"), item(1, "second section", "b")]
    assert len(expand(adjacent, [0, 1], 30).windows) == 2


def test_clipping_preserves_explicit_anchor_and_exact_source_offsets():
    source = item(0, "prefix " * 30 + "THE EVIDENCE" + " suffix" * 30)
    start = source.evidence.quote.index("THE EVIDENCE")
    hit = ContextHit(
        ref=source.evidence.ref, span=TextSpan(start=start, end=start + 12)
    )
    result = expand_structured_context(
        [source],
        [hit],
        policy=ContextExpansionPolicy(max_chars=20),
        allowed_refs=[source.evidence.ref],
    )
    window = result.windows[0]
    assert len(window.text) == 20 and "THE EVIDENCE" in window.text
    fragment = window.fragments[0]
    assert (
        source.evidence.quote[fragment.item_span.start : fragment.item_span.end]
        == fragment.evidence.quote
        == window.text
    )
    assert fragment.evidence.locator == TextSpan(
        start=100 + fragment.item_span.start, end=100 + fragment.item_span.end
    )
    result = expand_structured_context(
        [source],
        [hit],
        policy=ContextExpansionPolicy(max_chars=5),
        allowed_refs=[source.evidence.ref],
    )
    assert result.windows == () and result.over_budget_refs == (source.evidence.ref,)


def test_permissions_and_revisions_are_hard_boundaries_and_empty_figures_survive():
    items = [
        item(0, "public"),
        item(1, "SECRET"),
        item(2, "tail"),
        item(3, "", label="picture"),
    ]
    allowed = [i.evidence.ref for i in items if i.ordinal != 1]
    result = expand_structured_context(
        items,
        [ContextHit(ref=i.evidence.ref) for i in items],
        policy=ContextExpansionPolicy(max_chars=100),
        allowed_refs=allowed,
    )
    assert result.unavailable_refs == (items[1].evidence.ref,)
    assert all("SECRET" not in window.text for window in result.windows)
    assert all(
        not ({"0", "2"} <= {f.evidence.ref.unit_id for f in w.fragments})
        for w in result.windows
    )
    assert any(
        f.evidence.ref == items[3].evidence.ref
        for w in result.windows
        for f in w.fragments
    )
    revisions = [item(0, "old"), item(0, "new", revision="r2")]
    assert len(expand(revisions, [0, 1], 100).windows) == 2


def test_semantic_atom_bridge_uses_existing_source_coordinates():
    source = "# Heading\n\nFirst paragraph.\n\nSecond paragraph."
    document = parse_markdown(source, artifact_id="doc", revision="r1").values[0]
    atoms = semantic_atoms(document)
    items = context_items_from_atoms(
        atoms, source=ObjectRef(namespace="docs", object_id="doc")
    )
    result = expand(items, [0], 100)
    for fragment in result.windows[0].fragments:
        locator = fragment.evidence.locator
        assert isinstance(locator, TextSpan)
        assert source[locator.start : locator.end] == fragment.evidence.quote


def test_randomized_windows_never_lose_hits_or_misreport_fragments():
    rng = random.Random(804)
    for _ in range(150):
        items = [
            item(i, chr(65 + i) * rng.randrange(1, 80), str(i // 3)) for i in range(8)
        ]
        selected = sorted(rng.sample(range(8), rng.randrange(1, 8)))
        budget = rng.randrange(1, 100)
        result = expand(items, selected, budget)
        expected = {items[index].evidence.ref for index in selected}
        assert {
            ref for window in result.windows for ref in window.matched_refs
        } == expected
        for window in result.windows:
            assert len(window.text) <= budget
            fragment_refs = {fragment.evidence.ref for fragment in window.fragments}
            assert set(window.matched_refs) <= fragment_refs
            for fragment in window.fragments:
                original = next(
                    i for i in items if i.evidence.ref == fragment.evidence.ref
                )
                assert (
                    original.evidence.quote[
                        fragment.item_span.start : fragment.item_span.end
                    ]
                    == fragment.evidence.quote
                )
                assert fragment.evidence.quote in window.text


def test_bad_inputs_are_rejected():
    a = item(0, "hello")
    with pytest.raises(ValueError, match="unique"):
        expand([a, a], [0], 10)
    with pytest.raises(ValueError, match="ordinal"):
        expand([a, replace(item(1, "world"), ordinal=0)], [0], 10)
    with pytest.raises(ValueError, match="positive"):
        ContextExpansionPolicy(max_chars=0)
