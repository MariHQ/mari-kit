from __future__ import annotations

import pytest

from mari_components.errors import MalformedModelOutput
from mari_components.evaluation import (
    PairedMetric,
    RepeatedTrialResult,
    ReviewLabel,
    compare_paired_metrics,
    summarize_repeated_trials,
    summarize_review_reliability,
)
from mari_components.knowledge import (
    ExpertFeedback,
    FeedbackRootCause,
    KnowledgeFile,
    KnowledgeUse,
    TrajectoryEvidence,
    build_knowledge_use_manifest,
    inspect_knowledge_structure,
    parse_experience_knowledge,
    parse_feedback_diagnoses,
    parse_knowledge_change,
)
from mari_components.retrieval import (
    ContextUse,
    InformationRequirement,
    RequirementAssessment,
    RequirementStatus,
    assess_context_sufficiency,
    contextual_representation,
    evaluate_context_contribution,
    parse_retrieval_gap_queries,
    pool_token_spans,
)
from mari_components.trajectories import (
    IntentCandidate,
    IntentEvidence,
    IntentKind,
    cluster_intents,
    inspect_trace_integrity,
    mine_outcome_associations,
    normalize_genai_trace,
    parse_episode_reflection,
    parse_turn_assessments,
    project_tool_trajectory,
    segment_episodes,
)
from mari_components.trajectories.normalize import normalize_steps
from mari_components.trajectories.process import TrajectoryRun
from mari_components.types import KnowledgeDocument, KnowledgeSection


def _run(identifier: str, tools: list[str], outcome: str) -> TrajectoryRun:
    return TrajectoryRun(
        trajectory_id=identifier,
        steps=normalize_steps({"name": tool, "ok": True} for tool in tools),
        outcome=outcome,
    )


def test_trace_adapter_discards_captured_content_and_preserves_unknown_outcome() -> (
    None
):
    trace = normalize_genai_trace(
        {
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "schemaUrl": "https://opentelemetry.io/schemas/1.42.0",
                            "spans": [
                                {
                                    "traceId": "trace-1",
                                    "spanId": "span-1",
                                    "name": "call",
                                    "startTimeUnixNano": "1000000000",
                                    "endTimeUnixNano": "2000000000",
                                    "attributes": {
                                        "gen_ai.operation.name": "execute_tool",
                                        "gen_ai.tool.name": "search",
                                        "gen_ai.prompt": "private query",
                                        "gen_ai.request.model": "small-model",
                                    },
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    )
    assert trace.events[0].outcome is None
    assert "gen_ai.prompt" not in trace.events[0].attributes
    assert trace.events[0].attributes["gen_ai.request.model"] == "small-model"
    assert inspect_trace_integrity(trace).valid
    assert project_tool_trajectory(trace).steps[0].ok is None


def test_contrastive_patterns_are_descriptive_and_evidence_addressable() -> None:
    runs = (
        _run("s1", ["search", "answer"], "success"),
        _run("s2", ["search", "answer"], "success"),
        _run("f1", ["search", "retry", "answer"], "failure"),
        _run("f2", ["search", "retry", "answer"], "failure"),
    )
    retry = next(
        item for item in mine_outcome_associations(runs) if item.pattern == ("retry",)
    )
    assert retry.failure_risk_ratio > 1
    assert retry.failing_trajectory_ids == ("f1", "f2")


def test_knowledge_candidates_diagnoses_structure_and_edits_are_bounded() -> None:
    run = _run("run-1", ["lookup", "answer"], "failure")
    manifest = build_knowledge_use_manifest(
        run,
        [
            KnowledgeUse(
                artifact_id="policy",
                revision="r1",
                first_step=0,
                last_step=1,
                use="answer",
            )
        ],
    )
    feedback = ExpertFeedback(
        feedback_id="fb-1",
        correction="Use the enterprise limit.",
        evidence=TrajectoryEvidence(trajectory_id="run-1", start=1, end=1),
    )
    diagnoses = parse_feedback_diagnoses(
        [run],
        [manifest],
        [feedback],
        {
            "diagnoses": [
                {
                    "feedback_id": "fb-1",
                    "root_cause": "procedure_gap",
                    "could_resolve_from_loaded_knowledge": True,
                    "supporting_artifact_ids": ["policy"],
                    "explanation": "The policy was loaded but the wrong tier was selected.",
                }
            ]
        },
    )
    assert diagnoses[0].root_cause is FeedbackRootCause.PROCEDURE_GAP
    with pytest.raises(MalformedModelOutput):
        parse_feedback_diagnoses(
            [run],
            [manifest],
            [feedback],
            {
                "diagnoses": [
                    {
                        "feedback_id": "fb-1",
                        "root_cause": "procedure_gap",
                        "could_resolve_from_loaded_knowledge": True,
                        "supporting_artifact_ids": ["never-loaded"],
                        "explanation": "Invented citation",
                    }
                ]
            },
        )
    candidates = parse_experience_knowledge(
        [run],
        {
            "knowledge": [
                {
                    "kind": "pitfall",
                    "title": "Select a tier before reading limits",
                    "content": "Identify the customer tier before applying a limit.",
                    "evidence": [{"trajectory_id": "run-1", "start": 0, "end": 1}],
                    "applicability": ["tiered policies"],
                    "limitations": ["requires tier metadata"],
                }
            ]
        },
    )
    assert candidates[0].evidence[0].trajectory_id == "run-1"
    structure = inspect_knowledge_structure(
        [
            KnowledgeFile(
                artifact_id="a", revision="1", token_count=10, depends_on=("b",)
            ),
            KnowledgeFile(artifact_id="b", revision="1", token_count=10),
        ]
    )
    assert not structure.valid
    document = KnowledgeDocument(
        source_id="docs",
        external_id="policy",
        title="Policy",
        body="Limit is 10.",
        revision="r1",
    )
    proposal = parse_knowledge_change(
        {document.document_id: document},
        diagnoses,
        {
            "diagnosis_ids": ["fb-1"],
            "edits": [
                {
                    "document_id": document.document_id,
                    "original": "Limit is 10.",
                    "replacement": "Enterprise limit is 20.",
                    "reason": "Clarify the tier.",
                }
            ],
            "affected_artifact_ids": ["policy"],
        },
    )
    assert proposal.edits[0].source_revision == "r1"


def test_sufficiency_context_representations_and_contribution() -> None:
    requirements = (
        InformationRequirement(requirement_id="plan", description="customer plan"),
        InformationRequirement(requirement_id="limit", description="plan limit"),
    )
    report = assess_context_sufficiency(
        requirements,
        [
            RequirementAssessment(
                requirement_id="plan",
                status=RequirementStatus.SUPPORTED,
                evidence_ids=("doc:1",),
            )
        ],
    )
    assert report.required_coverage == 0.5
    assert parse_retrieval_gap_queries(
        report,
        {"queries": [{"query": "enterprise plan limit", "requirement_ids": ["limit"]}]},
    )[0].requirement_ids == ("limit",)
    contribution = evaluate_context_contribution(
        [
            ContextUse(item_id="a", token_count=200),
            ContextUse(item_id="b", token_count=800),
        ],
        used_ids=["a"],
        observed_utility=0.8,
        ablated_utility={"a": 0.5},
    )
    assert contribution.utilization == 0.2
    assert contribution.ablation_deltas["a"] == pytest.approx(0.3)
    document = KnowledgeDocument(
        source_id="docs",
        external_id="1",
        title="T",
        body="before\nTarget fact\nafter",
        revision="r1",
    )
    section = KnowledgeSection(
        document_id=document.document_id,
        section_id="s",
        title="S",
        body="Target fact",
        revision="s1",
        start=7,
        end=18,
    )
    representation = contextual_representation(
        section, "This section defines the current limit."
    )
    assert representation.original_text == "Target fact"
    assert representation.evidence_start == 7
    assert pool_token_spans([[1, 0], [3, 2]], [(0, 2)]) == ((2.0, 1.0),)


def test_intent_clusters_and_evaluation_statistics() -> None:
    candidates = tuple(
        IntentCandidate(
            candidate_id=identifier,
            intent=label,
            kind=IntentKind.INFERRED,
            evidence=(IntentEvidence(trajectory_id="t", start=0, end=0),),
        )
        for identifier, label in (
            ("a", "reset password"),
            ("b", "recover login"),
            ("c", "cancel account"),
        )
    )
    clustering = cluster_intents(
        candidates,
        {"a": [1, 0], "b": [0.99, 0.01], "c": [0, 1]},
        similarity_threshold=0.9,
    )
    assert sorted(cluster.support for cluster in clustering.clusters) == [1, 2]
    comparison = compare_paired_metrics(
        [
            PairedMetric(case_id="1", baseline=0.2, candidate=0.8),
            PairedMetric(case_id="2", baseline=0.5, candidate=0.5),
        ],
        bootstrap_samples=100,
        seed=2,
    )
    assert (comparison.wins, comparison.ties, comparison.losses) == (1, 1, 0)
    reliability = summarize_review_reliability(
        [
            ReviewLabel(item_id="a", reviewer_id="r1", label="keep"),
            ReviewLabel(item_id="a", reviewer_id="r2", label="keep"),
        ]
    )
    assert reliability.observed_agreement == 1
    repeated = summarize_repeated_trials(
        [RepeatedTrialResult(task_id="t", attempts=(True, False))]
    )
    assert repeated.pass_at_least_k[2] == 1
    assert repeated.pass_all_k[2] == 0


def test_episode_reflection_stays_bound_to_known_episode_ranges() -> None:
    run = _run("long-run", ["search", "read", "retry", "answer"], "success")
    turns = parse_turn_assessments(
        run,
        {
            "turns": [
                {
                    "start": 0,
                    "end": 1,
                    "situation": "Policy needed",
                    "intent": "Find the policy",
                    "action": "Search and read",
                    "assessment": "success",
                    "goal_progress": "Found a relevant revision",
                    "evidence_steps": [0, 1],
                },
                {
                    "start": 2,
                    "end": 3,
                    "situation": "Answer needed",
                    "intent": "Verify and answer",
                    "action": "Retry and answer",
                    "assessment": "partial",
                    "evidence_steps": [2, 3],
                },
            ]
        },
    )
    episodes = segment_episodes(run, turns, boundaries=[0, 1])
    reflection = parse_episode_reflection(
        episodes[0],
        [episodes[1]],
        {
            "comparison_episode_ids": [episodes[1].episode_id],
            "applicability": ["policy lookup"],
            "hints": ["Read the located revision before answering"],
            "pitfalls": ["A retry is not evidence of correctness"],
            "confidence": 0.8,
        },
    )
    assert reflection.comparison_episode_ids == (episodes[1].episode_id,)
    assert episodes[1].outcome.value == "partial"
