"""Prove that retrieval and answer caching share one authorization boundary."""

from __future__ import annotations

import json
import os
from collections.abc import Collection, Mapping

import numpy as np

from examples.support import selected_mode
from mari_components import DocumentACL, KnowledgeDocument, Principal
from mari_components.knowledge import parse_answer
from mari_components.retrieval import build_index, search_index
from mari_components.trajectories import (
    ReviewedWorkflow,
    WorkflowAction,
    WorkflowPolicy,
    build_reviewed_workflow_index,
    decide_reviewed_workflow,
)

PUBLIC_STATUS = KnowledgeDocument(
    source_id="status",
    external_id="checkout",
    title="Checkout service status",
    body="Customers experiencing checkout errors should follow updates on the status page.",
    revision="status-v2",
    acl=DocumentACL(visibility="public"),
)
INTERNAL_RUNBOOK = KnowledgeDocument(
    source_id="github:acme/operations",
    external_id="checkout-failover",
    title="Checkout failover runbook",
    body="On-call engineers mitigate checkout saturation by shifting traffic to the warm region.",
    revision="runbook-v8",
    acl=DocumentACL(
        visibility="restricted",
        principals=(Principal(kind="team", identifier="sre"),),
    ),
)
DOCUMENTS = (PUBLIC_STATUS, INTERNAL_RUNBOOK)
QUERY = np.asarray([[1.0, 0.0, 0.0, 0.0]], np.float32)


def _allowed_document_ids(
    principals: Collection[Principal],
) -> frozenset[str]:
    identities = frozenset(principals)
    return frozenset(
        document.document_id
        for document in DOCUMENTS
        if document.acl.visibility == "public"
        or bool(identities.intersection(document.acl.principals))
    )


def _answer(document: KnowledgeDocument, answer: str):
    return parse_answer(
        "How should checkout errors be handled?",
        (document,),
        {
            "answer": answer,
            "evidence": [{"document_id": document.document_id, "quote": document.body}],
        },
    )


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    mode = selected_mode(env)
    document_index = build_index(
        {
            PUBLIC_STATUS.document_id: np.asarray([[0.92, 0.08, 0.0, 0.0]], np.float32),
            INTERNAL_RUNBOOK.document_id: np.asarray(
                [[1.0, 0.0, 0.0, 0.0]], np.float32
            ),
        }
    )
    workflows = (
        ReviewedWorkflow(
            identifier="public-checkout-status",
            name="Give customers the public checkout status guidance",
            match_vectors=((0.92, 0.08, 0.0, 0.0),),
            document_ids=(PUBLIC_STATUS.document_id,),
            cached_answer=_answer(
                PUBLIC_STATUS,
                "Follow checkout incident updates on the public status page.",
            ),
        ),
        ReviewedWorkflow(
            identifier="internal-checkout-mitigation",
            name="Give on-call engineers the checkout mitigation",
            match_vectors=((1.0, 0.0, 0.0, 0.0),),
            document_ids=(INTERNAL_RUNBOOK.document_id,),
            cached_answer=_answer(
                INTERNAL_RUNBOOK,
                "Shift checkout traffic to the warm region.",
            ),
        ),
    )
    workflow_index = build_reviewed_workflow_index(workflows)
    revisions = {document.document_id: document.revision for document in DOCUMENTS}
    policy = WorkflowPolicy(speculation_threshold=0.70, cache_threshold=0.97)

    employee_allowed = _allowed_document_ids(
        (Principal(kind="team", identifier="sre"),)
    )
    customer_allowed = _allowed_document_ids(())
    employee_hits = search_index(
        document_index,
        QUERY,
        limit=2,
        allowed_document_ids=employee_allowed,
    )
    customer_hits = search_index(
        document_index,
        QUERY,
        limit=2,
        allowed_document_ids=customer_allowed,
    )
    employee_cache = decide_reviewed_workflow(
        QUERY,
        workflow_index,
        revisions,
        allowed_document_ids=employee_allowed,
        policy=policy,
    )
    customer_cache = decide_reviewed_workflow(
        QUERY,
        workflow_index,
        revisions,
        allowed_document_ids=customer_allowed,
        policy=policy,
    )
    employee_answer = (
        employee_cache.cached_answer.answer if employee_cache.cached_answer else ""
    )
    customer_answer = (
        customer_cache.cached_answer.answer if customer_cache.cached_answer else ""
    )
    return {
        "mode": mode,
        "employee_allowed_document_ids": tuple(sorted(employee_allowed)),
        "customer_allowed_document_ids": tuple(sorted(customer_allowed)),
        "employee_retrieval_hits": tuple(row.document_id for row in employee_hits),
        "customer_retrieval_hits": tuple(row.document_id for row in customer_hits),
        "employee_cache_action": employee_cache.action.value,
        "customer_cache_action": customer_cache.action.value,
        "employee_workflow": (
            employee_cache.match.workflow.identifier if employee_cache.match else ""
        ),
        "customer_workflow": (
            customer_cache.match.workflow.identifier if customer_cache.match else ""
        ),
        "employee_answer": employee_answer,
        "customer_answer": customer_answer,
        "restricted_document_hidden_from_customer": (
            INTERNAL_RUNBOOK.document_id not in customer_allowed
            and INTERNAL_RUNBOOK.document_id
            not in {row.document_id for row in customer_hits}
            and "warm region" not in customer_answer
        ),
        "both_users_received_grounded_cache": (
            employee_cache.action is WorkflowAction.CACHED_RESPONSE
            and customer_cache.action is WorkflowAction.CACHED_RESPONSE
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
