"""Independent algorithm choices, using fixture callbacks and no storage/model.

Run ``python -m examples.algorithm_choices_demo``; add ``--solvers`` after
installing ``mari-components[algorithm-solvers]`` for native graph/linkage choices.
See docs/algorithm-choices.md for pinned project and paper references.
"""

from __future__ import annotations

import argparse
import io
import json

from mari_components.algorithms.compression import (
    TextSpan,
    fastcdc_chunks,
    select_surprising_words,
)
from mari_components.algorithms.graph_retrieval import (
    UnionCandidate,
    hipporag_seed_weights,
    rank_candidate_union,
    weighted_chunk_polling,
)
from mari_components.algorithms.lexical import BM25Variant, BM25VariantIndex
from mari_components.algorithms.linkage import BlockingPredicate, learn_blocking
from mari_components.algorithms.memory import (
    MemoryNote,
    NoteUpdate,
    evolve_neighborhood,
    memory_heat,
)
from mari_components.algorithms.search import (
    DriftQuery,
    DriftResponse,
    drift_search,
    refine_extraction,
)
from mari_components.algorithms.subsets import (
    FacilityLocation,
    GreedyMethod,
    maximize_subset,
)
from mari_components.algorithms.temporal import recency_decay, temporal_proof_score
from mari_components.retrieval.graph import personalized_pagerank


def run(*, include_solvers: bool = False) -> dict[str, object]:
    documents = {"a": "retrieval graph graph".split(), "b": "retrieval lexical".split()}
    lexical = {
        variant.value: [
            (hit.item_id, round(hit.score, 4))
            for hit in BM25VariantIndex(documents, variant=variant).search(["graph"])
        ]
        for variant in BM25Variant
    }
    objective = FacilityLocation([[1, 0.1, 0.5], [0.1, 1, 0.5]])
    choices = {
        method.value: maximize_subset(
            3, objective.evaluate, budget=2, method=method, assume_submodular=True
        ).selected
        for method in GreedyMethod
    }
    allowed = {"entity:a", "entity:b", "passage:a", "passage:b"}
    seeds = hipporag_seed_weights(
        [("entity:a", "entity:b", 0.8)],
        entity_passage_counts={"entity:a": 2, "entity:b": 1},
        passage_scores={"passage:a": 0.9, "passage:b": 0.3},
        allowed_nodes=allowed,
    )
    propagated = personalized_pagerank(
        {"entity:a": {"passage:a": 1}, "entity:b": {"passage:b": 1}},
        {seed.node: seed.weight for seed in seeds},
        allowed_node_ids=allowed,
    )
    drift = drift_search(
        "explain retrieval",
        primer=lambda _: [DriftQuery("graph retrieval", 0.8)],
        local_search=lambda query, depth: DriftResponse(
            query.query, (DriftQuery("lexical retrieval", 0.6),) if depth == 0 else ()
        ),
        reduce=lambda _, actions: " / ".join(
            action.response.answer for action in actions if action.response is not None
        ),
    )
    extracted = refine_extraction(
        "graph retrieval",
        extract=lambda _: [("graph", "entity")],
        refine=lambda *_: [("retrieval", "technique")],
        key=lambda row: row[0],
        merge=lambda _, new: new,
        max_rounds=2,
    )
    spans = [TextSpan(0, 5), TextSpan(6, 10)]
    compressed = select_surprising_words(
        "known rare", spans, spans, [0.9, 0.01], fraction=0.5
    )
    blocking = learn_blocking(
        [BlockingPredicate("name", frozenset({"match"}), 2)], frozenset({"match"})
    )
    changes = evolve_neighborhood(
        MemoryNote("new", 0, "new fact"),
        [MemoryNote("old", 1, "old fact")],
        propose=lambda *_: [NoteUpdate("new", 0, add_links=("old",))],
    )
    candidate = UnionCandidate("collection", "a", 1, (1.0, 0.0), "shared-model")
    union = rank_candidate_union(
        [candidate],
        allowed_keys={candidate.key},
        query_vector=[1.0, 0.0],
        query_space="shared-model",
    )
    result: dict[str, object] = {
        "lexical_variants": lexical,
        "subset_choices": choices,
        "graph_propagation_converged": propagated.converged,
        "drift_answer": drift.answer,
        "extracted_records": extracted.records,
        "chunk_allocation": weighted_chunk_polling(
            [["a"], ["b", "c"]], maximum=3
        ).chunks,
        "freshness_adjusted_score": temporal_proof_score(
            0.8, recency=recency_decay(90, method="exponential")
        ),
        "selected_text": compressed.text,
        "byte_chunks": len(tuple(fastcdc_chunks(io.BytesIO(b"content" * 1000)))),
        "heat": memory_heat(2, 3, 24),
        "blocking_predicates": blocking.predicates,
        "proposed_revision": changes[0].after.revision,
        "union_score": union[0].score,
    }
    if include_solvers:
        from mari_components.algorithms.graphs import (
            hierarchical_leiden_partition,
            louvain_partition,
            prize_collecting_forest,
        )
        from mari_components.algorithms.linkage import PairScore, centroid_clusters

        nodes = ["a", "b", "c"]
        edges = [("a", "b", 1.0), ("b", "c", 1.0)]
        result["pcst_nodes"] = prize_collecting_forest(
            {"a": 0, "b": 0, "c": 10}, edges, root="a"
        ).nodes
        result["louvain"] = louvain_partition(nodes, edges)
        result["leiden_final_nodes"] = [
            row.node
            for row in hierarchical_leiden_partition(nodes, edges, seed=42)
            if row.final
        ]
        result["centroid_members"] = [
            cluster.members for cluster in centroid_clusters([PairScore("a", "b", 0.9)])
        ]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solvers", action="store_true")
    print(json.dumps(run(include_solvers=parser.parse_args().solvers), indent=2))
