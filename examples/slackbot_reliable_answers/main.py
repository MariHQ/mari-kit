"""Slack answer with managed voice, speculative reads, and revision-safe reuse."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Mapping
from dataclasses import replace

import numpy as np

from examples.support import (
    json_generator,
    required,
    selected_mode,
    text_embedder,
    urllib_transport,
)
from mari_components import KnowledgeDocument, PollRequest
from mari_components.agents import AgentEvent, EventKind
from mari_components.connectors import GitHubConfig, poll_github, validate_github
from mari_components.retrieval import build_index, search_index
from mari_components.trajectories import (
    ReviewedWorkflow,
    WorkflowAction,
    WorkflowPolicy,
    build_reviewed_workflow_index,
    decide_reviewed_workflow,
    impacted_workflows,
    match_reviewed_workflow,
    parse_trajectory_analysis,
    start_speculative_retrieval,
)

STYLEGUIDE = KnowledgeDocument(
    source_id="mari",
    external_id="styleguide",
    title="Support voice",
    body="Be warm, direct, and concise. Begin affirmative answers with 'Absolutely'. "
    "Use one short paragraph and no exclamation points.",
    revision="style-v5",
)
REFUND_POLICY = KnowledgeDocument(
    source_id="mari",
    external_id="refund-policy",
    title="Enterprise refund policy",
    body="Enterprise customers may request a full refund within 30 days of purchase.",
    revision="refund-v3",
)
QUESTION = "Can an enterprise customer get a refund?"
NEARBY_QUESTION = "How do refunds work for enterprise customers?"
WORKFLOW_INTENT = "Answer enterprise customer refund policy questions"
WORKFLOW_PHASES = (
    "Retrieve the managed support voice styleguide",
    "Retrieve the current enterprise refund policy and answer with a citation",
)


def _fixture(_prompt: str, version: str) -> object:
    if version == "slackbot-grounded-answer-v1":
        return {
            "answer": "Absolutely — enterprise customers may request a full refund within "
            "30 days of purchase. [refund-policy]",
            "citations": ["refund-policy#p0"],
        }
    if version == "trajectory-mining-v2":
        return {
            "workflow": "A reviewed intent launched the managed-document read before the "
            "answer model ran. The answer cited the retrieved refund policy.",
            "activity": "Answer a support policy question from managed knowledge.",
            "category": "support-answer",
            "intent": "Answer refund policy question",
            "rework": 0,
            "phases": [
                {
                    "name": "Retrieve knowledge",
                    "family": "inspect",
                    "start": 0,
                    "end": 2,
                    "substate": "Completed",
                },
                {
                    "name": "Answer",
                    "family": "answer",
                    "start": 3,
                    "end": 3,
                    "substate": "Completed",
                },
            ],
        }
    raise AssertionError(version)


def _document(value: object) -> KnowledgeDocument:
    if not isinstance(value, dict):
        raise RuntimeError("managed documents must be JSON objects")
    return KnowledgeDocument(
        source_id=str(value.get("source_id") or "mari"),
        external_id=required(value, "external_id"),
        title=required(value, "title"),
        body=required(value, "body"),
        revision=required(value, "revision"),
        source_url=str(value.get("source_url") or ""),
    )


def _managed_documents(
    env: Mapping[str, str], mode: str
) -> tuple[KnowledgeDocument, ...]:
    if mode == "fake":
        return STYLEGUIDE, REFUND_POLICY
    repository = str(env.get("MARI_GITHUB_REPOSITORY") or "").strip()
    if repository:
        paths = tuple(
            value.strip()
            for value in required(env, "MARI_GITHUB_PATHS").split(",")
            if value.strip()
        )
        config = GitHubConfig(required(env, "GITHUB_TOKEN"), repository, paths=paths)
        validation = validate_github(config, http=urllib_transport)
        if not validation.ok:
            raise RuntimeError(validation.message)
        documents = tuple(
            document
            for page in poll_github(config, PollRequest(), http=urllib_transport)
            for document in page.upserts
        )
        if not documents:
            raise RuntimeError("GitHub returned no managed documents")
        return documents
    try:
        styleguide = json.loads(required(env, "MARI_STYLEGUIDE_JSON"))
        documents = json.loads(required(env, "MARI_DOCUMENTS_JSON"))
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "managed knowledge variables must contain valid JSON"
        ) from error
    if not isinstance(documents, list) or not documents:
        raise RuntimeError("MARI_DOCUMENTS_JSON must be a non-empty array")
    return (_document(styleguide), *(_document(value) for value in documents))


def _slack_input(env: Mapping[str, str], mode: str) -> tuple[str, str, str]:
    if mode == "fake":
        return "C-SUPPORT", "1710000000.000100", QUESTION
    if str(env.get("MARI_SLACK_POST") or "false").strip().casefold() != "true":
        return "dry-run", "dry-run", required(env, "MARI_QUESTION")
    try:
        payload = json.loads(required(env, "SLACK_EVENT_JSON"))
    except json.JSONDecodeError as error:
        raise RuntimeError("SLACK_EVENT_JSON must be valid JSON") from error
    event = payload.get("event") if isinstance(payload, dict) else None
    if not isinstance(event, dict):
        raise RuntimeError("SLACK_EVENT_JSON must contain an event object")
    thread = str(event.get("thread_ts") or event.get("ts") or "").strip()
    if not thread:
        raise RuntimeError("Slack event must contain ts or thread_ts")
    return required(event, "channel"), thread, required(event, "text")


def _answer_prompt(
    question: str,
    documents: tuple[KnowledgeDocument, ...],
    styleguide_id: str,
) -> str:
    styleguide = next(row for row in documents if row.document_id == styleguide_id)
    evidence = _evidence_blocks(documents, styleguide_id)
    return (
        "Use the styleguide only for voice and the product documents as the only facts. "
        "Apply every styleguide rule to the presentation. Return JSON with answer as a string "
        "and citations as an array of exact evidence_id strings. Cite only supplied evidence IDs.\n"
        f"Question: {question}\nStyleguide: {styleguide.body}\nEvidence: "
        + json.dumps(
            [
                {"evidence_id": evidence_id, "text": text}
                for evidence_id, (_document, text) in evidence.items()
            ]
        )
    )


def _evidence_blocks(
    documents: tuple[KnowledgeDocument, ...],
    styleguide_id: str,
) -> dict[str, tuple[KnowledgeDocument, str]]:
    evidence: dict[str, tuple[KnowledgeDocument, str]] = {}
    for document in documents:
        if document.document_id == styleguide_id:
            continue
        paragraphs = tuple(
            value.strip()
            for value in re.split(r"\n\s*\n", document.body)
            if value.strip()
        )
        for index, paragraph in enumerate(paragraphs):
            evidence[f"{document.external_id}#p{index}"] = (document, paragraph)
    return evidence


def _analysis_prompt(question: str, events: tuple[dict[str, object], ...]) -> str:
    return (
        "Label this completed trajectory. Return workflow, activity, category, intent, rework, "
        "and contiguous zero-based phases with name, family, start, end, and substate. "
        f"There are exactly {len(events)} events, indexed 0 through {len(events) - 1}; "
        "the phase ranges must cover every index exactly once with no gaps or overlap.\n"
        f"Question: {question}\nEvents: "
        + json.dumps([{"index": index, **event} for index, event in enumerate(events)])
    )


def _telemetry(events: tuple[AgentEvent, ...]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "name": event.name or event.kind.value,
            "args": dict(event.arguments),
            "summary": "answered"
            if event.kind is EventKind.ANSWER
            else event.kind.value,
            "ok": event.ok,
        }
        for event in events
    )


async def _retrieve_speculatively(
    decision,
    documents: Mapping[str, KnowledgeDocument],
) -> tuple[tuple[KnowledgeDocument, ...], bool]:
    started = asyncio.Event()

    async def retrieve(document_ids: tuple[str, ...]) -> tuple[KnowledgeDocument, ...]:
        started.set()
        await asyncio.sleep(0)
        return tuple(documents[document_id] for document_id in document_ids)

    task = start_speculative_retrieval(decision, retrieve)
    await started.wait()
    started_before_await = not task.done()
    return await task, started_before_await


def _post_slack(token: str, channel: str, thread: str, answer: str) -> str:
    from slack_sdk import WebClient

    response = WebClient(token=token).chat_postMessage(
        channel=channel,
        thread_ts=thread,
        text=answer,
    )
    return str(response["ts"])


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    mode = selected_mode(env)
    policy = WorkflowPolicy(
        speculation_threshold=float(required(env, "MARI_SPECULATION_THRESHOLD")),
        cache_threshold=float(required(env, "MARI_CACHE_THRESHOLD")),
        relevant_document_threshold=float(
            env.get("MARI_RELEVANT_DOCUMENT_THRESHOLD") or "0.85"
        ),
    )
    documents = _managed_documents(env, mode)
    by_id = {row.document_id: row for row in documents}
    configured_styleguide = str(env.get("MARI_STYLEGUIDE_DOCUMENT_ID") or "").strip()
    styleguide_id = configured_styleguide or next(
        (row.document_id for row in documents if row.external_id == "styleguide"),
        "",
    )
    if not styleguide_id:
        raise RuntimeError("managed knowledge must include the styleguide document")
    channel, thread, question = _slack_input(env, mode)

    embed = text_embedder(env)
    workflow_texts = (WORKFLOW_INTENT, *WORKFLOW_PHASES)
    document_texts = tuple(
        text for document in documents for text in (document.title, document.body)
    )
    texts = (*workflow_texts, question, NEARBY_QUESTION, *document_texts)
    vectors = embed(texts)
    workflow_vectors = vectors[: len(workflow_texts)]
    question_vector, nearby_vector = vectors[
        len(workflow_texts) : len(workflow_texts) + 2
    ]
    document_rows = vectors[len(workflow_texts) + 2 :]
    document_vectors = {
        row.document_id: np.asarray(
            document_rows[index * 2 : index * 2 + 2], np.float32
        )
        for index, row in enumerate(documents)
    }
    product_vectors = {
        document_id: value
        for document_id, value in document_vectors.items()
        if document_id != styleguide_id
    }
    document_hits = search_index(
        build_index(product_vectors),
        np.asarray((question_vector,), np.float32),
        limit=len(product_vectors),
    )
    relevant_scores = {hit.document_id: hit.score for hit in document_hits}

    seed = ReviewedWorkflow(
        identifier="support-refunds",
        name=WORKFLOW_INTENT,
        match_vectors=tuple(
            tuple(float(value) for value in row)
            for row in (*workflow_vectors, question_vector)
        ),
        document_ids=tuple(row.document_id for row in documents),
    )
    seed_index = build_reviewed_workflow_index((seed,))
    current_revisions = {row.document_id: row.revision for row in documents}
    decision = decide_reviewed_workflow(
        (question_vector,),
        seed_index,
        current_revisions,
        relevant_document_scores=relevant_scores,
        policy=policy,
    )
    events: list[AgentEvent] = []
    speculative_started = False
    if decision.action is WorkflowAction.SPECULATIVE_RETRIEVAL:
        events.append(
            AgentEvent(
                kind=EventKind.TOOL_PROPOSAL,
                name="retrieve_documents",
                arguments={
                    "workflow": seed.identifier,
                    "document_count": len(decision.document_ids),
                },
                speculative=True,
            )
        )
        events.append(
            AgentEvent(
                kind=EventKind.TOOL_CALL,
                name="retrieve_documents",
                arguments={"document_count": len(decision.document_ids)},
                speculative=True,
            )
        )
        selected, speculative_started = asyncio.run(
            _retrieve_speculatively(decision, by_id)
        )
    else:
        hit_id = document_hits[0].document_id
        selected = (by_id[styleguide_id], by_id[hit_id])
        events.append(
            AgentEvent(
                kind=EventKind.TOOL_CALL,
                name="retrieve_documents",
                arguments={"document_count": len(selected)},
            )
        )
    selected_ids = tuple(row.document_id for row in selected)
    events.append(
        AgentEvent(
            kind=EventKind.TOOL_RESULT,
            name="retrieve_documents",
            result={
                "documents": [
                    {"id": row.document_id, "revision": row.revision}
                    for row in selected
                ]
            },
            arguments={"document_count": len(selected)},
            speculative=speculative_started,
        )
    )

    generate = json_generator(env, _fixture)
    value = generate(
        _answer_prompt(question, selected, styleguide_id),
        "slackbot-grounded-answer-v1",
    )
    answer = str(value.get("answer") or "").strip() if isinstance(value, dict) else ""
    raw_citations = value.get("citations") if isinstance(value, dict) else None
    citation_rows = tuple(raw_citations) if isinstance(raw_citations, list) else ()
    evidence = _evidence_blocks(selected, styleguide_id)
    citations: list[str] = []
    verified_evidence = 0
    for citation in citation_rows:
        if not isinstance(citation, str) or citation not in evidence:
            raise RuntimeError("DeepSeek cited evidence that was not supplied")
        document, paragraph = evidence[citation]
        if paragraph not in document.body:
            raise RuntimeError("evidence block lost its source provenance")
        verified_evidence += 1
        citations.append(document.external_id)
    if not answer or not citations:
        raise RuntimeError("DeepSeek answer must cite retrieved evidence")
    events.append(AgentEvent(kind=EventKind.ANSWER, result=answer))

    telemetry = _telemetry(tuple(events))
    analysis_value = generate(
        _analysis_prompt(question, telemetry), "trajectory-mining-v2"
    )
    analysis = parse_trajectory_analysis(
        telemetry,
        analysis_value,
        family_map={"retrieve_documents": "inspect", "answer": "answer"},
    )

    cached = replace(
        seed,
        document_ids=selected_ids,
        cache_dependencies={row.document_id: row.revision for row in selected},
        cached_answer=answer,
    )
    cached_index = build_reviewed_workflow_index((cached,))
    cache_match = match_reviewed_workflow(
        (question_vector,),
        cached_index,
        minimum_score=-1,
    )
    cache_score = cache_match.score if cache_match else -1.0
    cache_decision = decide_reviewed_workflow(
        (question_vector,),
        cached_index,
        current_revisions,
        policy=policy,
    )
    nearby_decision = decide_reviewed_workflow(
        (nearby_vector,),
        cached_index,
        current_revisions,
        policy=policy,
    )

    changed_revisions = dict(current_revisions)
    changed_document = next(row for row in selected_ids if row != styleguide_id)
    changed_revisions[changed_document] += "-changed"
    changed_decision = decide_reviewed_workflow(
        (question_vector,),
        cached_index,
        changed_revisions,
        policy=policy,
    )
    impacted = impacted_workflows((cached,), changed_revisions)

    new_document = "mari/refund-exception"
    new_scores = {new_document: 0.99}
    unresolved_new = decide_reviewed_workflow(
        (question_vector,),
        cached_index,
        current_revisions,
        relevant_document_scores=new_scores,
        policy=policy,
    )
    nonimpacting_new = decide_reviewed_workflow(
        (question_vector,),
        cached_index,
        current_revisions,
        relevant_document_scores=new_scores,
        impact_decisions={new_document: False},
        policy=policy,
    )
    impacting_new = decide_reviewed_workflow(
        (question_vector,),
        cached_index,
        current_revisions,
        relevant_document_scores=new_scores,
        impact_decisions={new_document: True},
        policy=policy,
    )

    slack_timestamp = "fixture-post"
    if (
        mode == "live"
        and str(env.get("MARI_SLACK_POST") or "false").casefold() == "true"
    ):
        slack_timestamp = _post_slack(
            required(env, "SLACK_BOT_TOKEN"),
            channel,
            thread,
            answer,
        )
    style_checks = {"no_exclamation": "!" not in answer}
    if STYLEGUIDE.document_id == styleguide_id:
        style_checks["fixture_affirmative_opening"] = answer.startswith("Absolutely")
    else:
        style_checks.update(
            {
                "no_dash_punctuation": "—" not in answer and "–" not in answer,
                "no_marketing_fillers": not any(
                    word in answer.casefold()
                    for word in ("seamless", "robust", "leverage", "delve")
                ),
            }
        )
    return {
        "mode": mode,
        "deepseek_answer_rounds": 1,
        "deepseek_analysis_rounds": 1,
        "openai_embedding_calls": 1,
        "styleguide_revision": by_id[styleguide_id].revision,
        "styleguide_applied": all(style_checks.values()),
        "styleguide_checks": style_checks,
        "speculative_tool_called": speculative_started,
        "speculation_reason": decision.reason.value,
        "speculation_score": round(decision.match.score if decision.match else -1, 4),
        "retrieved_document_ids": selected_ids,
        "trajectory_steps": len(analysis.steps),
        "trajectory_phases": tuple(phase.name for phase in analysis.phases),
        "trajectory_analyzed_after_answer": events[-1].kind is EventKind.ANSWER,
        "cache_threshold": policy.cache_threshold,
        "cache_score": round(cache_score, 4),
        "cache_hit": cache_decision.action is WorkflowAction.CACHED_RESPONSE,
        "nearby_query_action": nearby_decision.action.value,
        "cached_response": cache_decision.cached_answer,
        "changed_document": changed_document,
        "impacted_workflows": impacted,
        "action_after_document_change": changed_decision.action.value,
        "new_document_unreviewed_action": unresolved_new.action.value,
        "new_document_nonimpacting_action": nonimpacting_new.action.value,
        "new_document_impacting_action": impacting_new.action.value,
        "slack_post_timestamp": slack_timestamp,
        "answer": answer,
        "citations": tuple(dict.fromkeys(citations)),
        "verified_evidence_blocks": verified_evidence,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
