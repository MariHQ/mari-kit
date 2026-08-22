"""Extract and independently cache grounded answers inside one workflow."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

from examples.support import json_generator, required, selected_mode, text_embedder
from mari_components import KnowledgeDocument
from mari_components.errors import MalformedModelOutput
from mari_components.knowledge import impacted_artifacts, parse_answer
from mari_components.trajectories import (
    ReviewedWorkflow,
    WorkflowAction,
    WorkflowPolicy,
    build_reviewed_workflow_index,
    decide_reviewed_workflow,
    match_reviewed_workflow,
    parse_trajectory_analysis,
)

ENTITLEMENTS = KnowledgeDocument(
    source_id="mari",
    external_id="plan-entitlements",
    title="Plan entitlements",
    body="The Business and Enterprise plans include SSO.",
    revision="entitlements-v4",
)
SETUP = KnowledgeDocument(
    source_id="mari",
    external_id="sso-setup",
    title="Configure SSO",
    body="Workspace admins configure SSO in Settings > Security > Single sign-on.",
    revision="setup-v7",
)
DOCUMENTS = (ENTITLEMENTS, SETUP)
ORIGINAL_REQUEST = (
    "Can Acme on the Business plan use SSO, and where does an admin configure it?"
)
ENTITLEMENT_QUESTION = "Does the Business plan include SSO?"
SETUP_QUESTION = "Where does an admin configure SSO?"
PARAPHRASE = "Does the Business plan include SSO access?"
REVIEWED_CACHE_KEYS = frozenset({"sso-entitlement", "sso-setup"})

EVENTS: tuple[dict[str, object], ...] = (
    {
        "name": "lookup_account",
        "args": {"account": "Acme"},
        "summary": "Found the Business plan for the account.",
        "ok": True,
    },
    {
        "name": "search_product_knowledge",
        "args": {"topic": "SSO plan eligibility"},
        "summary": "Found the plan-entitlements document.",
        "ok": True,
    },
    {
        "name": "read_document",
        "args": {"document_id": ENTITLEMENTS.document_id},
        "summary": "Read the current plan entitlement.",
        "ok": True,
    },
    {
        "name": "search_product_knowledge",
        "args": {"topic": "SSO configuration"},
        "summary": "Found the SSO setup document.",
        "ok": True,
    },
    {
        "name": "read_document",
        "args": {"document_id": SETUP.document_id},
        "summary": "Read the current setup path.",
        "ok": True,
    },
    {
        "name": "answer",
        "args": {},
        "summary": "Answered eligibility and setup with citations.",
        "ok": True,
    },
)


def _fixture(_prompt: str, version: str) -> object:
    if version == "workflow-view-layer1-v1":
        return {
            "description": "The agent identified Acme's plan, checked whether that plan "
            "includes SSO, found the administrator setup path, and combined both results.",
            "phases": [
                {
                    "name": "Resolve SSO entitlement",
                    "family": "inspect",
                    "start": 0,
                    "end": 2,
                    "substate": "Completed",
                },
                {
                    "name": "Find SSO setup path",
                    "family": "inspect",
                    "start": 3,
                    "end": 4,
                    "substate": "Completed",
                },
                {
                    "name": "Compose customer answer",
                    "family": "answer",
                    "start": 5,
                    "end": 5,
                    "substate": "Completed",
                },
            ],
            "cache_candidates": [
                {
                    "cache_key": "sso-entitlement",
                    "phase": "Resolve SSO entitlement",
                    "question": ENTITLEMENT_QUESTION,
                    "answer": {
                        "answer": "Yes. The Business plan includes SSO.",
                        "disposition": "grounded",
                        "evidence": [
                            {
                                "document_id": ENTITLEMENTS.document_id,
                                "quote": ENTITLEMENTS.body,
                            }
                        ],
                    },
                },
                {
                    "cache_key": "sso-setup",
                    "phase": "Find SSO setup path",
                    "question": SETUP_QUESTION,
                    "answer": {
                        "answer": "An admin configures SSO in Settings > Security > "
                        "Single sign-on.",
                        "disposition": "grounded",
                        "evidence": [
                            {"document_id": SETUP.document_id, "quote": SETUP.body}
                        ],
                    },
                },
            ],
        }
    if version == "workflow-view-layer2-v1":
        return {
            "workflow": "Resolve a customer's feature eligibility and provide the "
            "relevant administrator configuration path.",
            "activity": "Answer an account-specific SSO eligibility and setup question.",
            "category": "support-configuration",
            "intent": "Resolve SSO availability and setup",
            "rework": 0,
        }
    raise AssertionError(version)


def _layer1_prompt() -> str:
    return (
        "Convert these chronological support-agent actions into a detailed grounded "
        "description and contiguous activity phases. Identify independently reusable "
        "question/answer candidates only when an answer is fully supported by an exact "
        "quote from the supplied documents. Return JSON with description, phases, and "
        "cache_candidates. Each phase needs name, family, start, end, and substate. Each "
        "candidate needs cache_key, phase, question, and an answer object with answer, "
        "disposition, and evidence entries containing document_id and exact quote. "
        "cache_key must be sso-entitlement or sso-setup.\n"
        f"Request: {ORIGINAL_REQUEST}\n"
        f"Events: {json.dumps([{'index': i, **row} for i, row in enumerate(EVENTS)])}\n"
        f"Documents: {json.dumps([{'document_id': row.document_id, 'title': row.title, 'body': row.body} for row in DOCUMENTS])}"
    )


def _layer2_prompt(description: str) -> str:
    return (
        "Infer the high-level activity from this detailed workflow description only. "
        "Return JSON with workflow, activity, category, intent, and non-negative rework.\n"
        f"Detailed workflow: {description}"
    )


def _required_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MalformedModelOutput(f"{label} must be a JSON object")
    return value


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    selected_mode(env)
    generate = json_generator(env, _fixture)

    layer1 = _required_object(
        generate(_layer1_prompt(), "workflow-view-layer1-v1"), "WorkflowView layer 1"
    )
    description = str(layer1.get("description") or "").strip()
    if not description:
        raise MalformedModelOutput("WorkflowView layer 1 description is required")
    layer2 = _required_object(
        generate(_layer2_prompt(description), "workflow-view-layer2-v1"),
        "WorkflowView layer 2",
    )
    analysis = parse_trajectory_analysis(
        EVENTS,
        {**layer2, "phases": layer1.get("phases")},
        family_map={
            "lookup_account": "inspect",
            "search_product_knowledge": "inspect",
            "read_document": "inspect",
            "answer": "answer",
        },
    )

    raw_candidates = layer1.get("cache_candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise MalformedModelOutput("WorkflowView must return cache candidates")
    phases = {phase.name: phase for phase in analysis.phases}
    candidates: list[tuple[str, str, str, object]] = []
    seen_cache_keys: set[str] = set()
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            raise MalformedModelOutput("cache candidates must be objects")
        cache_key = str(raw.get("cache_key") or "").strip()
        phase_name = str(raw.get("phase") or "").strip()
        question = str(raw.get("question") or "").strip()
        if cache_key not in REVIEWED_CACHE_KEYS or cache_key in seen_cache_keys:
            raise MalformedModelOutput(
                "cache candidate key is unreviewed or duplicated"
            )
        if phase_name not in phases or not question:
            raise MalformedModelOutput("cache candidate must reference a known phase")
        answer = parse_answer(question, DOCUMENTS, raw.get("answer"))
        phase = phases[phase_name]
        read_document_ids = {
            str(analysis.steps[index].arguments.get("document_id") or "")
            for index in range(phase.start, phase.end + 1)
            if analysis.steps[index].tool == "read_document"
        }
        if any(row.document_id not in read_document_ids for row in answer.evidence):
            raise MalformedModelOutput(
                "cache candidate evidence was not read inside its activity phase"
            )
        seen_cache_keys.add(cache_key)
        candidates.append((cache_key, phase_name, question, answer))

    embed = text_embedder(env)
    embedding_inputs = tuple(
        text
        for _cache_key, phase_name, question, _answer in candidates
        for text in (question, phase_name)
    ) + (ENTITLEMENT_QUESTION, SETUP_QUESTION, ORIGINAL_REQUEST, PARAPHRASE)
    vectors = embed(embedding_inputs)
    workflows: list[ReviewedWorkflow] = []
    for index, (cache_key, phase_name, _question, answer) in enumerate(candidates):
        document_ids = tuple(
            dict.fromkeys(row.document_id for row in answer.knowledge_dependencies)
        )
        workflows.append(
            ReviewedWorkflow(
                identifier=cache_key,
                name=phase_name,
                match_vectors=(vectors[index * 2], vectors[index * 2 + 1]),
                document_ids=document_ids,
                cached_answer=answer,
            )
        )

    index = build_reviewed_workflow_index(workflows)
    query_vectors = vectors[len(candidates) * 2 :]
    revisions = {row.document_id: row.revision for row in DOCUMENTS}
    threshold = float(required(env, "MARI_CACHE_THRESHOLD"))
    policy = WorkflowPolicy(speculation_threshold=0.70, cache_threshold=threshold)
    entitlement = decide_reviewed_workflow(
        (query_vectors[0],), index, revisions, policy=policy
    )
    setup = decide_reviewed_workflow(
        (query_vectors[1],), index, revisions, policy=policy
    )
    compound = decide_reviewed_workflow(
        (query_vectors[2],), index, revisions, policy=policy
    )

    paraphrase_match = match_reviewed_workflow(
        (query_vectors[3],), index, minimum_score=-1
    )
    if paraphrase_match is None:
        raise RuntimeError("MUVERA did not return a workflow match")
    strict_threshold = min(1.0, paraphrase_match.score + 0.01)
    relaxed_threshold = max(-1.0, paraphrase_match.score - 0.01)
    strict = decide_reviewed_workflow(
        (query_vectors[3],),
        index,
        revisions,
        policy=WorkflowPolicy(
            speculation_threshold=-1.0, cache_threshold=strict_threshold
        ),
    )
    relaxed = decide_reviewed_workflow(
        (query_vectors[3],),
        index,
        revisions,
        policy=WorkflowPolicy(
            speculation_threshold=-1.0, cache_threshold=relaxed_threshold
        ),
    )

    changed_revisions = dict(revisions)
    changed_revisions[ENTITLEMENTS.document_id] = "entitlements-v5"
    impacted = impacted_artifacts(
        {
            f"workflow:{workflow.identifier}": (
                workflow.cached_answer.knowledge_dependencies
                if workflow.cached_answer
                else ()
            )
            for workflow in workflows
        },
        changed_revisions,
    )
    entitlement_after_change = decide_reviewed_workflow(
        (query_vectors[0],), index, changed_revisions, policy=policy
    )
    setup_after_change = decide_reviewed_workflow(
        (query_vectors[1],), index, changed_revisions, policy=policy
    )

    return {
        "mode": selected_mode(env),
        "deepseek_layer_rounds": 2,
        "openai_embedding_calls": 1,
        "events": len(analysis.steps),
        "workflow": analysis.grounded_workflow,
        "activity": analysis.activity,
        "extracted_phases": tuple(phase.name for phase in analysis.phases),
        "cacheable_steps": tuple(row.identifier for row in workflows),
        "entitlement_cache_hit": entitlement.action is WorkflowAction.CACHED_RESPONSE,
        "setup_cache_hit": setup.action is WorkflowAction.CACHED_RESPONSE,
        "entitlement_answer": (
            entitlement.cached_answer.answer if entitlement.cached_answer else ""
        ),
        "setup_answer": setup.cached_answer.answer if setup.cached_answer else "",
        "compound_request_action": compound.action.value,
        "paraphrase_score": round(paraphrase_match.score, 4),
        "strict_threshold": round(strict_threshold, 4),
        "strict_threshold_action": strict.action.value,
        "relaxed_threshold": round(relaxed_threshold, 4),
        "relaxed_threshold_action": relaxed.action.value,
        "impacted_after_entitlement_change": tuple(impacted),
        "entitlement_after_change": entitlement_after_change.action.value,
        "setup_after_change": setup_after_change.action.value,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
