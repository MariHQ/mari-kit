"""Build an evidence-linked employee-onboarding company brain.

This module is credential-free. Every model output is a deterministic fixture,
and the host supplies the principal-to-document authorization decision. It
exercises four behaviors an onboarding brain needs:

- facts bound to exact Markdown sections,
- policy edits that invalidate only the edited section,
- unchanged-section reuse across a document revision change,
- missing/invalid evidence and restricted HR documents.

Run ``python -m examples.company_brains.onboarding`` to print JSON.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

import numpy as np

from mari_kit import (
    DocumentACL,
    Evidence,
    FactCandidate,
    KnowledgeDocument,
    Principal,
)
from mari_kit.errors import MalformedModelOutput
from mari_kit.knowledge import (
    AnswerDisposition,
    assess_freshness,
    deduplicate_fact_candidates,
    parse_answer,
    parse_claim_assessments,
    parse_facts,
    parse_refinement,
    pending_fact_sections,
    section_revisions,
)
from mari_kit.retrieval import build_index, search_index

HANDBOOK_V1 = KnowledgeDocument(
    source_id="handbook",
    external_id="onboarding",
    title="Employee onboarding handbook",
    body=(
        "# Welcome\n"
        "New hires complete onboarding within their first two weeks.\n\n"
        "# Equipment\n"
        "Standard onboarding equipment is a laptop and a monitor.\n\n"
        "# Security training\n"
        "All employees complete security training every year.\n"
    ),
    revision="handbook-v1",
    acl=DocumentACL(visibility="public"),
)
IT_GUIDE = KnowledgeDocument(
    source_id="handbook",
    external_id="it-setup",
    title="IT setup guide",
    body=(
        "# Accounts\n"
        "IT provisions accounts on the first day.\n\n"
        "# Access\n"
        "Access requests require manager approval.\n"
    ),
    revision="it-v1",
    acl=DocumentACL(visibility="public"),
)
HR_POLICY = KnowledgeDocument(
    source_id="handbook",
    external_id="hr-policy",
    title="People operations policy",
    body=(
        "# Leave\n"
        "Full-time employees accrue paid time off each pay period.\n\n"
        "# Benefits\n"
        "Benefits enrollment closes thirty days after the start date.\n\n"
        "# Compensation\n"
        "Compensation reviews occur every year.\n"
    ),
    revision="hr-v1",
    acl=DocumentACL(
        visibility="restricted",
        principals=(Principal(kind="team", identifier="people-ops"),),
    ),
)
DOCUMENTS = (HANDBOOK_V1, IT_GUIDE, HR_POLICY)

_ENGINEER = Principal(kind="team", identifier="engineering")
_PEOPLE_OPS = Principal(kind="team", identifier="people-ops")

# The restricted HR document is the strongest lexical match, so a leaking
# authorization filter would surface it first.
_RETRIEVAL_QUERY = np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
_RETRIEVAL_INDEX = build_index(
    {
        HANDBOOK_V1.document_id: np.asarray([[0.2, 0.9, 0.0, 0.0]], np.float32),
        IT_GUIDE.document_id: np.asarray([[0.1, 0.0, 0.9, 0.0]], np.float32),
        HR_POLICY.document_id: np.asarray([[1.0, 0.0, 0.0, 0.0]], np.float32),
    }
)

# Deterministic stand-in for model extraction. Each quote is an exact section
# substring, so the parser recomputes the span and section revision itself.
_ONBOARDING_ROWS = {
    "facts": [
        {
            "claim": "New hires complete onboarding within their first two weeks.",
            "subject": {"canonical": "new hires"},
            "relation": "complete_onboarding_within",
            "object": "two weeks",
            "evidence": [
                {
                    "document_id": HANDBOOK_V1.document_id,
                    "quote": "New hires complete onboarding within their first two weeks.",
                    "section_id": "welcome",
                }
            ],
        },
        {
            "claim": "Standard onboarding equipment is a laptop and a monitor.",
            "subject": {"canonical": "onboarding equipment"},
            "relation": "includes",
            "object": ["laptop", "monitor"],
            "evidence": [
                {
                    "document_id": HANDBOOK_V1.document_id,
                    "quote": "Standard onboarding equipment is a laptop and a monitor.",
                    "section_id": "equipment",
                }
            ],
        },
        {
            "claim": "All employees complete security training every year.",
            "subject": {"canonical": "security training"},
            "relation": "recurrence",
            "object": "yearly",
            "evidence": [
                {
                    "document_id": HANDBOOK_V1.document_id,
                    "quote": "All employees complete security training every year.",
                    "section_id": "security-training",
                }
            ],
        },
    ]
}
_HR_ROWS = {
    "facts": [
        {
            "claim": "Benefits enrollment closes thirty days after the start date.",
            "evidence": [
                {
                    "document_id": HR_POLICY.document_id,
                    "quote": "Benefits enrollment closes thirty days after the start date.",
                    "section_id": "benefits",
                }
            ],
        }
    ]
}
_POLICY_EDIT = {
    "edits": [
        {
            "original": "Standard onboarding equipment is a laptop and a monitor.",
            "replacement": (
                "Standard onboarding equipment is a laptop, a monitor, "
                "and a security key."
            ),
            "reason": "Security upgraded onboarding hardware.",
        }
    ]
}


def handbook_facts() -> tuple[FactCandidate, ...]:
    """Return the validated deterministic onboarding facts."""
    return parse_facts((HANDBOOK_V1,), _ONBOARDING_ROWS)


def hr_facts() -> tuple[FactCandidate, ...]:
    """Return the validated restricted HR facts."""
    return parse_facts((HR_POLICY,), _HR_ROWS)


def proposed_policy_edit():
    """Return the reviewed policy-edit proposal that produces handbook v2."""
    return parse_refinement(HANDBOOK_V1, _POLICY_EDIT)


def handbook_after_edit() -> KnowledgeDocument:
    """Apply the reviewed exact-substring edit to produce the next revision."""
    edit = proposed_policy_edit()[0]
    return KnowledgeDocument(
        source_id=HANDBOOK_V1.source_id,
        external_id=HANDBOOK_V1.external_id,
        title=HANDBOOK_V1.title,
        body=HANDBOOK_V1.body.replace(edit.original, edit.replacement, 1),
        revision="handbook-v2",
        acl=HANDBOOK_V1.acl,
    )


def host_allowed_document_ids(
    principals: Collection[Principal],
) -> frozenset[str]:
    """Host-owned mapping from provider ACLs to an authorization decision.

    Mari records provider metadata; the application decides who may read it.
    """
    identities = frozenset(principals)
    return frozenset(
        document.document_id
        for document in DOCUMENTS
        if document.acl.visibility == "public"
        or bool(identities.intersection(document.acl.principals))
    )


def serve_facts(
    facts: Iterable[FactCandidate],
    allowed_document_ids: Collection[str],
) -> tuple[FactCandidate, ...]:
    """Keep only facts whose evidence is fully inside the authorized set."""
    allowed = frozenset(allowed_document_ids)
    return tuple(
        fact
        for fact in facts
        if all(item.document_id in allowed for item in fact.evidence)
    )


def _checkpoints(facts: Iterable[FactCandidate]) -> dict[tuple[str, str], str]:
    return {
        (item.document_id, item.section_id): item.section_revision
        for fact in facts
        for item in fact.evidence
    }


def run() -> dict[str, object]:
    facts = handbook_facts()
    edit = proposed_policy_edit()[0]
    revised = handbook_after_edit()
    current_revisions = {
        revised.document_id: revised.revision,
        IT_GUIDE.document_id: IT_GUIDE.revision,
        HR_POLICY.document_id: HR_POLICY.revision,
    }
    current_sections = section_revisions((revised, IT_GUIDE, HR_POLICY))
    previous_sections = section_revisions((HANDBOOK_V1,))
    current_handbook_sections = section_revisions((revised,))
    changed_sections = tuple(
        sorted(
            f"{document_id}#{section_id}"
            for (document_id, section_id), revision in (
                current_handbook_sections.items()
            )
            if previous_sections.get((document_id, section_id)) != revision
        )
    )

    section_status = {
        fact.evidence[0].section_id: assess_freshness(
            fact.evidence,
            current_revisions,
            current_section_revisions=current_sections,
        ).status.value
        for fact in facts
    }
    fallback_status = assess_freshness(
        facts[0].evidence, current_revisions
    ).status.value

    checkpoints = _checkpoints(facts)
    pending = pending_fact_sections((revised,), checkpoints, limit=10)
    pending_ids = tuple(
        f"{section.document_id}#{section.section_id}" for section in pending
    )
    reused = tuple(
        fact.claim
        for fact in facts
        if f"{fact.evidence[0].document_id}#{fact.evidence[0].section_id}"
        not in pending_ids
    )

    unknown_document_rejected = False
    try:
        parse_facts(
            (HANDBOOK_V1,),
            {
                "facts": [
                    {
                        "claim": "Unverifiable.",
                        "evidence": [
                            {
                                "document_id": "handbook/retired",
                                "quote": "Unverifiable.",
                            }
                        ],
                    }
                ]
            },
        )
    except MalformedModelOutput:
        unknown_document_rejected = True

    invented_quote_rejected = False
    try:
        parse_facts(
            (HANDBOOK_V1,),
            {
                "facts": [
                    {
                        "claim": "All employees complete security training every month.",
                        "evidence": [
                            {
                                "document_id": HANDBOOK_V1.document_id,
                                "quote": "All employees complete security training every month.",
                            }
                        ],
                    }
                ]
            },
        )
    except MalformedModelOutput:
        invented_quote_rejected = True

    downgraded = parse_claim_assessments(
        ("All employees complete security training every year.",),
        (HANDBOOK_V1,),
        {
            "assessments": [
                {
                    "claim": "All employees complete security training every year.",
                    "verdict": "supported",
                    "explanation": "Audit quote.",
                    "evidence": [
                        {
                            "document_id": HANDBOOK_V1.document_id,
                            "quote": "All employees complete security training monthly.",
                        }
                    ],
                }
            ]
        },
    )[0]

    abstention = parse_answer(
        "What is the annual travel stipend?",
        DOCUMENTS,
        {
            "answer": "The supplied onboarding knowledge does not state a stipend.",
            "disposition": AnswerDisposition.INSUFFICIENT_EVIDENCE.value,
            "evidence": [],
        },
    )

    missing = assess_freshness(
        (
            Evidence(
                document_id="handbook/retired-benefits",
                revision="v1",
                quote="Retired benefit.",
            ),
        ),
        current_revisions,
    )

    duplicate_reuse = deduplicate_fact_candidates(
        facts, existing_claims=[fact.claim for fact in facts]
    )

    employee_allowed = host_allowed_document_ids((_ENGINEER,))
    people_ops_allowed = host_allowed_document_ids((_PEOPLE_OPS,))
    employee_hits = search_index(
        _RETRIEVAL_INDEX,
        _RETRIEVAL_QUERY,
        limit=3,
        allowed_document_ids=employee_allowed,
    )
    people_ops_hits = search_index(
        _RETRIEVAL_INDEX,
        _RETRIEVAL_QUERY,
        limit=3,
        allowed_document_ids=people_ops_allowed,
    )
    employee_facts = serve_facts((*facts, *hr_facts()), employee_allowed)

    return {
        "handbook_fact_claims": tuple(fact.claim for fact in facts),
        "handbook_fact_sections": tuple(fact.evidence[0].section_id for fact in facts),
        "proposed_policy_edit": {
            "original": edit.original,
            "replacement": edit.replacement,
            "reason": edit.reason,
        },
        "changed_sections": changed_sections,
        "section_status_after_edit": section_status,
        "document_level_fallback_status": fallback_status,
        "pending_sections_after_edit": pending_ids,
        "reused_unchanged_section_facts": reused,
        "unknown_document_citation_rejected": unknown_document_rejected,
        "invented_quote_rejected": invented_quote_rejected,
        "unverifiable_assessment_verdict": downgraded.verdict,
        "insufficient_evidence_disposition": abstention.disposition.value,
        "missing_evidence_status": missing.status.value,
        "duplicate_reuse_count": len(duplicate_reuse),
        "employee_allowed_documents": tuple(sorted(employee_allowed)),
        "people_ops_allowed_documents": tuple(sorted(people_ops_allowed)),
        "employee_retrieval_hits": tuple(row.document_id for row in employee_hits),
        "people_ops_retrieval_hits": tuple(row.document_id for row in people_ops_hits),
        "restricted_hr_hidden_from_employee": (
            HR_POLICY.document_id not in employee_allowed
            and HR_POLICY.document_id not in {row.document_id for row in employee_hits}
        ),
        "employee_served_documents": tuple(
            fact.evidence[0].document_id for fact in employee_facts
        ),
        "employee_served_hr_facts": any(
            fact.evidence[0].document_id == HR_POLICY.document_id
            for fact in employee_facts
        ),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run(), indent=2))
