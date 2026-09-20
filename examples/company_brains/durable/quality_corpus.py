"""Host-owned quality corpus for the durable company brain wave-2 contract.

This module is deliberately data-only: it never calls a model and never opens a
network connection. Each case pairs a natural-language question with the
documents a host would authorize for one request, plus evaluator-only labels.
The labels exist to grade predictions in :mod:`quality_eval`; they must never be
placed in a model prompt.

``build_prompt`` is the only supported path from a case to model input. It
returns exactly the question and the authorized documents, which keeps hidden
grading fields (expected disposition, required/forbidden terms, and the allowed
evidence set) out of prompts by construction. Authorization is explicit here:
documents absent from ``authorized_document_ids`` are part of the host corpus
(for example restricted evidence or a superseded revision) but are withheld
from the prompt.

Mari Kit records provider ACL observations but never turns them into an access
decision, so the corpus stores the already-decided visible set. The labels are
lexical proxies only; they cannot prove semantic correctness.
"""

from __future__ import annotations

from collections.abc import Iterable

from mari_kit import DocumentACL, KnowledgeDocument, Principal

CATEGORIES: tuple[str, ...] = (
    "current_policy",
    "superseded_policy",
    "conflict",
    "ambiguity",
    "missing_info",
    "restricted_evidence",
    "irrelevant_matches",
)

DISPOSITIONS: tuple[str, ...] = ("grounded", "insufficient_evidence")

ABSTENTION_TEXT = "No authorized evidence supports an answer to this question."

# Evaluator-only case fields. ``build_prompt`` must never expose these.
GRADING_FIELDS: frozenset[str] = frozenset(
    {
        "expected_disposition",
        "required_terms",
        "forbidden_terms",
        "allowed_evidence_ids",
        "allowed_evidence_refs",
    }
)


def _doc(
    source_id: str,
    external_id: str,
    title: str,
    body: str,
    revision: str,
    *,
    visibility: str = "connector_scope",
    principals: tuple[Principal, ...] = (),
    updated_at: str = "",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=source_id,
        external_id=external_id,
        title=title,
        body=body,
        revision=revision,
        acl=DocumentACL(visibility=visibility, principals=principals),
        updated_at=updated_at,
    )


def _ids(documents: Iterable[KnowledgeDocument]) -> list[str]:
    return [document.document_id for document in documents]


def _case(
    case_id: str,
    category: str,
    question: str,
    *,
    documents: tuple[KnowledgeDocument, ...],
    expected_disposition: str,
    required_terms: tuple[str, ...] = (),
    forbidden_terms: tuple[str, ...] = (),
    allowed_evidence: tuple[KnowledgeDocument, ...] = (),
    authorized: tuple[KnowledgeDocument, ...] | None = None,
) -> dict:
    if category not in CATEGORIES:
        raise ValueError(f"unknown quality category: {category!r}")
    if expected_disposition not in DISPOSITIONS:
        raise ValueError(f"unknown disposition: {expected_disposition!r}")
    corpus = tuple(documents)
    identities = {(document.document_id, document.revision) for document in corpus}
    if len(identities) != len(corpus):
        raise ValueError(f"case {case_id!r} repeats a document revision")
    visible = corpus if authorized is None else tuple(authorized)
    if not all(any(item is candidate for candidate in corpus) for item in visible):
        raise ValueError(f"case {case_id!r} authorizes documents outside its corpus")
    visible_identities = {
        (document.document_id, document.revision) for document in visible
    }
    allowed_ids = _ids(allowed_evidence)
    if (
        not {(document.document_id, document.revision) for document in allowed_evidence}
        <= visible_identities
    ):
        raise ValueError(f"case {case_id!r} allows unauthorized evidence")
    if expected_disposition == "grounded" and not allowed_ids:
        raise ValueError(f"grounded case {case_id!r} requires allowed evidence")
    if expected_disposition == "insufficient_evidence" and allowed_ids:
        raise ValueError(f"abstaining case {case_id!r} cannot allow evidence")
    return {
        "id": case_id,
        "category": category,
        "question": question,
        "documents": corpus,
        "authorized_documents": visible,
        "authorized_document_ids": _ids(visible),
        "expected_disposition": expected_disposition,
        "required_terms": list(required_terms),
        "forbidden_terms": list(forbidden_terms),
        "allowed_evidence_ids": allowed_ids,
        "allowed_evidence_refs": [
            {"document_id": document.document_id, "revision": document.revision}
            for document in allowed_evidence
        ],
    }


def authorized_documents(case: dict) -> tuple[KnowledgeDocument, ...]:
    """Return the documents a host has authorized for this case's request.

    Authorization is keyed by object identity, not by ``document_id``: a
    superseded revision shares a ``document_id`` with the current one but must
    still be withheld, so filtering by ID alone would leak the retired body.
    """

    return tuple(case["authorized_documents"])


def build_prompt(case: dict) -> dict:
    """Return only the question and authorized input documents.

    The returned mapping has exactly the keys ``question`` and ``documents``.
    Evaluator-only fields are unreachable from the result, so a caller cannot
    accidentally smuggle gold labels into a model prompt through this path.
    """

    return {
        "question": case["question"],
        "documents": authorized_documents(case),
    }


_REFUND_CURRENT = _doc(
    "handbook",
    "refunds",
    "Enterprise refund policy",
    "Enterprise customers may request a refund within 45 days of invoice. "
    "After 45 days, requests require finance approval.",
    "refund-v3",
    updated_at="2025-02-01T00:00:00Z",
)
_REFUND_SUPERSEDED = _doc(
    "handbook",
    "refunds",
    "Enterprise refund policy",
    "Enterprise customers may request a refund within 30 days of invoice.",
    "refund-v2",
)
_SHIPPING = _doc(
    "handbook",
    "shipping",
    "Shipping policy",
    "Standard shipping arrives in three business days; overnight is available "
    "for an extra fee.",
    "shipping-v1",
)

_SECURITY_MFA = _doc(
    "security",
    "mfa-policy",
    "Multi-factor authentication policy",
    "All employees must use phishing-resistant MFA, such as passkeys or "
    "hardware security keys, for single sign-on. SMS codes are not accepted.",
    "mfa-v1",
)
_SECURITY_OFFBOARDING = _doc(
    "security",
    "offboarding",
    "Offboarding checklist",
    "Revoke SSO sessions, rotate shared secrets, and return hardware on the "
    "employee's last day.",
    "offboard-v1",
)

_HR_PTO = _doc(
    "hr",
    "pto",
    "Paid time off policy",
    "Employees receive 25 days of paid time off per calendar year. Unused PTO "
    "carries over up to 5 days.",
    "pto-v1",
)

_SLA = _doc(
    "support",
    "sla",
    "Support response targets",
    "Priority 1 incidents receive a first response within 15 minutes and a "
    "status update every 30 minutes.",
    "sla-v1",
)
_SLA_DISTRACTOR = _doc(
    "support",
    "tiers",
    "Support tiers",
    "Priority levels range from Priority 1, the most severe, to Priority 4, a "
    "general question.",
    "tiers-v1",
)

_PASSWORD_CURRENT = _doc(
    "security",
    "password-policy",
    "Password policy",
    "Passwords must not be rotated on a fixed schedule; rotate credentials only "
    "when compromise is suspected.",
    "password-v2",
)
_PASSWORD_SUPERSEDED = _doc(
    "security",
    "password-policy",
    "Password policy",
    "Passwords must be rotated every 90 days.",
    "password-v1",
)

_LOGS_CURRENT = _doc(
    "platform",
    "log-retention",
    "Log retention",
    "Production logs are retained for 13 months and then deleted.",
    "logs-v2",
)
_LOGS_SUPERSEDED = _doc(
    "platform",
    "log-retention",
    "Log retention",
    "Production logs are retained for 30 days.",
    "logs-v1",
)

_TRAVEL_CURRENT = _doc(
    "finance",
    "travel-policy",
    "Travel policy",
    "Flights longer than six hours may be booked in premium economy. All other "
    "flights are booked economy.",
    "travel-v2",
)
_TRAVEL_SUPERSEDED = _doc(
    "finance",
    "travel-policy",
    "Travel policy",
    "All flights must be booked in economy class.",
    "travel-v1",
)

_EXPENSE_FINANCE = _doc(
    "finance",
    "expenses",
    "Finance expense policy",
    "Client meals are reimbursed up to $75 per person when itemized.",
    "expense-v5",
    updated_at="2025-01-10T00:00:00Z",
)
_EXPENSE_SALES = _doc(
    "sales",
    "playbook",
    "Sales playbook",
    "Client meals are reimbursed up to $150 per person during deal cycles.",
    "playbook-v2",
    updated_at="2024-06-01T00:00:00Z",
)

_DEPLOY_ENG = _doc(
    "engineering",
    "change-freeze",
    "Change freeze policy",
    "A company-wide change freeze runs from December 20 to January 2. Emergency "
    "changes require the CTO.",
    "freeze-v4",
    updated_at="2025-03-01T00:00:00Z",
)
_DEPLOY_PRODUCT = _doc(
    "product",
    "release-notes",
    "Release notes",
    "Deploys during the winter freeze are allowed with VP approval.",
    "notes-v1",
    updated_at="2024-02-01T00:00:00Z",
)

_NDA_LEGAL = _doc(
    "legal",
    "nda-policy",
    "NDA policy",
    "Every mutual NDA must be reviewed by legal before signature.",
    "nda-v3",
    updated_at="2025-04-01T00:00:00Z",
)
_NDA_SALES = _doc(
    "sales",
    "nda-faq",
    "NDA FAQ",
    "Standard NDAs under $10k need no review.",
    "ndafaq-v1",
    updated_at="2023-09-01T00:00:00Z",
)

_LEAVE_MEDICAL = _doc(
    "hr",
    "medical-leave",
    "Medical leave",
    "Medical leave runs for 12 weeks with job protection.",
    "medical-v1",
)
_LEAVE_PARENTAL = _doc(
    "hr",
    "parental-leave",
    "Parental leave",
    "Parental leave runs for 16 weeks for all new parents.",
    "parental-v1",
)

_REFUND_US = _doc(
    "handbook",
    "refunds-us",
    "US refunds",
    "US customers have a 30 day refund window.",
    "refundus-v1",
)
_REFUND_EU = _doc(
    "handbook",
    "refunds-eu",
    "EU refunds",
    "EU customers have a 14 day refund window.",
    "refundeu-v1",
)

_ESCALATION_SEV1 = _doc(
    "support",
    "sev1",
    "Severity 1 escalation",
    "Severity 1 incidents are escalated to the on-call engineer within 15 minutes.",
    "sev1-v1",
)
_ESCALATION_SEV2 = _doc(
    "support",
    "sev2",
    "Severity 2 escalation",
    "Severity 2 incidents are escalated within four hours.",
    "sev2-v1",
)

_SOC2_CERT = _doc(
    "compliance",
    "certifications",
    "Certifications",
    "The company holds ISO 27001 certification.",
    "certs-v1",
)

_HOLIDAYS_2026 = _doc(
    "hr",
    "holidays-2026",
    "2026 holiday calendar",
    "The 2026 company holidays are New Year's Day, Memorial Day, Independence "
    "Day, Thanksgiving, and Christmas.",
    "holidays-v2026",
)

_PLATFORM_TEAMS = _doc(
    "engineering",
    "teams",
    "Engineering teams",
    "The platform group owns shared services. Team size changes each quarter.",
    "teams-v1",
)

_COMP_RESTRICTED = _doc(
    "hr",
    "compensation",
    "Compensation bands",
    "The Staff engineer salary band is $210,000 to $260,000.",
    "comp-v1",
    visibility="restricted",
    principals=(Principal(kind="team", identifier="people"),),
)
_LEGAL_RESTRICTED = _doc(
    "legal",
    "acme-settlement",
    "Acme settlement memo",
    "The Acme settlement pays $1.2M in three installments.",
    "acme-v1",
    visibility="restricted",
    principals=(Principal(kind="team", identifier="legal"),),
)
_INCIDENT_RESTRICTED = _doc(
    "ops",
    "march-postmortem",
    "March outage postmortem",
    "The March outage was caused by an expired TLS certificate.",
    "march-v1",
    visibility="restricted",
    principals=(Principal(kind="team", identifier="oncall"),),
)
_ROADMAP_RESTRICTED = _doc(
    "product",
    "roadmap-q3",
    "Q3 roadmap",
    "The billing rewrite ships in September.",
    "roadmap-q3",
    visibility="restricted",
    principals=(Principal(kind="team", identifier="product"),),
)

_GIFTCARD_REFUNDS = _doc(
    "handbook",
    "refunds-physical",
    "Physical goods refunds",
    "Refunds apply to physical goods returned within 45 days. Digital gift "
    "cards are non-refundable and final sale.",
    "physical-v1",
)
_GIFTCARD_PURCHASE = _doc(
    "handbook",
    "gift-cards",
    "Gift card purchases",
    "Gift cards can be purchased in denominations from $10 to $500.",
    "giftbuy-v1",
)

_PARKING_EMPLOYEE = _doc(
    "facilities",
    "parking",
    "Employee parking",
    "Employees park in the south garage using a badge. Carpool spots are "
    "reserved on level two.",
    "parking-v1",
)
_PARKING_TRANSIT = _doc(
    "facilities",
    "transit",
    "Transit benefits",
    "Employees may enroll in a pre-tax transit benefit.",
    "transit-v1",
)

_REMOTE_STIPEND = _doc(
    "hr",
    "remote-work",
    "Remote work policy",
    "Remote employees receive a one-time home office equipment stipend of $500.",
    "remote-v1",
)
_REMOTE_HOURS = _doc(
    "hr",
    "core-hours",
    "Core hours",
    "All employees overlap at least four hours with 10:00 to 16:00 local time.",
    "corehours-v1",
)

_RELEASE_41 = _doc(
    "engineering",
    "release-4.1",
    "Release 4.1 notes",
    "Release 4.1 requires Java 17 and Node 20.",
    "rel41-v1",
)
_RELEASE_42 = _doc(
    "engineering",
    "release-4.2",
    "Release 4.2 notes",
    "Release 4.2 requires Node 22 and ships the new scheduler.",
    "rel42-v1",
)


def cases() -> list[dict]:
    """Return the labeled quality corpus (>= 24 cases across seven categories)."""

    return [
        _case(
            "current.refund_window",
            "current_policy",
            "How long is the enterprise refund window?",
            documents=(_REFUND_CURRENT, _SHIPPING),
            expected_disposition="grounded",
            required_terms=("45 days",),
            forbidden_terms=("30 days", "60 days", "90 days"),
            allowed_evidence=(_REFUND_CURRENT,),
        ),
        _case(
            "current.mfa",
            "current_policy",
            "What multi-factor authentication does the company require for SSO?",
            documents=(_SECURITY_MFA, _SECURITY_OFFBOARDING),
            expected_disposition="grounded",
            required_terms=("phishing-resistant", "passkeys"),
            forbidden_terms=("sms codes are accepted",),
            allowed_evidence=(_SECURITY_MFA,),
        ),
        _case(
            "current.pto",
            "current_policy",
            "How many paid time off days do employees receive per year?",
            documents=(_HR_PTO,),
            expected_disposition="grounded",
            required_terms=("25 days",),
            forbidden_terms=("20 days", "30 days"),
            allowed_evidence=(_HR_PTO,),
        ),
        _case(
            "current.sev1_sla",
            "current_policy",
            "What is the first response target for Priority 1 incidents?",
            documents=(_SLA, _SLA_DISTRACTOR),
            expected_disposition="grounded",
            required_terms=("15 minutes",),
            forbidden_terms=("1 hour", "4 hours"),
            allowed_evidence=(_SLA,),
        ),
        _case(
            "superseded.refund_window",
            "superseded_policy",
            "How long is the enterprise refund window today?",
            documents=(_REFUND_SUPERSEDED, _REFUND_CURRENT),
            expected_disposition="grounded",
            required_terms=("45 days",),
            forbidden_terms=("30 days",),
            allowed_evidence=(_REFUND_CURRENT,),
            authorized=(_REFUND_CURRENT,),
        ),
        _case(
            "superseded.password_rotation",
            "superseded_policy",
            "What is the current password rotation requirement?",
            documents=(_PASSWORD_SUPERSEDED, _PASSWORD_CURRENT),
            expected_disposition="grounded",
            required_terms=("not be rotated on a fixed schedule",),
            forbidden_terms=("every 90 days",),
            allowed_evidence=(_PASSWORD_CURRENT,),
            authorized=(_PASSWORD_CURRENT,),
        ),
        _case(
            "superseded.log_retention",
            "superseded_policy",
            "How long are production logs retained now?",
            documents=(_LOGS_SUPERSEDED, _LOGS_CURRENT),
            expected_disposition="grounded",
            required_terms=("13 months",),
            forbidden_terms=("30 days",),
            allowed_evidence=(_LOGS_CURRENT,),
            authorized=(_LOGS_CURRENT,),
        ),
        _case(
            "superseded.travel_class",
            "superseded_policy",
            "When may employees book premium economy flights?",
            documents=(_TRAVEL_SUPERSEDED, _TRAVEL_CURRENT),
            expected_disposition="grounded",
            required_terms=("six hours", "premium economy"),
            forbidden_terms=("economy class",),
            allowed_evidence=(_TRAVEL_CURRENT,),
            authorized=(_TRAVEL_CURRENT,),
        ),
        _case(
            "conflict.client_meals",
            "conflict",
            "What is the per-person reimbursement limit for client meals?",
            documents=(_EXPENSE_SALES, _EXPENSE_FINANCE),
            expected_disposition="insufficient_evidence",
        ),
        _case(
            "conflict.change_freeze",
            "conflict",
            "When does the winter change freeze start?",
            documents=(_DEPLOY_PRODUCT, _DEPLOY_ENG),
            expected_disposition="grounded",
            required_terms=("december 20",),
            forbidden_terms=("vp approval",),
            allowed_evidence=(_DEPLOY_ENG,),
        ),
        _case(
            "conflict.nda_review",
            "conflict",
            "What approval is required before signing a mutual NDA?",
            documents=(_NDA_SALES, _NDA_LEGAL),
            expected_disposition="insufficient_evidence",
        ),
        _case(
            "ambiguity.leave_length",
            "ambiguity",
            "How long is leave?",
            documents=(_LEAVE_MEDICAL, _LEAVE_PARENTAL),
            expected_disposition="insufficient_evidence",
        ),
        _case(
            "ambiguity.refund_region",
            "ambiguity",
            "What is the refund window?",
            documents=(_REFUND_US, _REFUND_EU),
            expected_disposition="insufficient_evidence",
        ),
        _case(
            "ambiguity.escalation",
            "ambiguity",
            "Without guessing severity, give the single escalation deadline for this incident.",
            documents=(_ESCALATION_SEV1, _ESCALATION_SEV2),
            expected_disposition="insufficient_evidence",
        ),
        _case(
            "missing.soc2",
            "missing_info",
            "Is the company SOC 2 certified?",
            documents=(_SOC2_CERT,),
            expected_disposition="insufficient_evidence",
        ),
        _case(
            "missing.holidays",
            "missing_info",
            "What are the 2027 company holidays?",
            documents=(_HOLIDAYS_2026,),
            expected_disposition="insufficient_evidence",
        ),
        _case(
            "missing.headcount",
            "missing_info",
            "How many engineers are on the platform team?",
            documents=(_PLATFORM_TEAMS,),
            expected_disposition="insufficient_evidence",
        ),
        _case(
            "restricted.compensation",
            "restricted_evidence",
            "What is the Staff engineer salary band?",
            documents=(_COMP_RESTRICTED, _HR_PTO),
            expected_disposition="insufficient_evidence",
            authorized=(_HR_PTO,),
        ),
        _case(
            "restricted.settlement",
            "restricted_evidence",
            "What are the settlement terms in the Acme lawsuit?",
            documents=(_LEGAL_RESTRICTED, _NDA_LEGAL),
            expected_disposition="insufficient_evidence",
            authorized=(_NDA_LEGAL,),
        ),
        _case(
            "restricted.outage_cause",
            "restricted_evidence",
            "What caused the March outage?",
            documents=(_INCIDENT_RESTRICTED, _SLA),
            expected_disposition="insufficient_evidence",
            authorized=(_SLA,),
        ),
        _case(
            "restricted.roadmap",
            "restricted_evidence",
            "When will the billing rewrite ship?",
            documents=(_ROADMAP_RESTRICTED, _NDA_LEGAL),
            expected_disposition="insufficient_evidence",
            authorized=(_NDA_LEGAL,),
        ),
        _case(
            "irrelevant.giftcard_refund",
            "irrelevant_matches",
            "Can a digital gift card be refunded?",
            documents=(_GIFTCARD_REFUNDS, _GIFTCARD_PURCHASE),
            expected_disposition="grounded",
            required_terms=("non-refundable",),
            allowed_evidence=(_GIFTCARD_REFUNDS,),
        ),
        _case(
            "irrelevant.visitor_parking",
            "irrelevant_matches",
            "Where can visitors park at headquarters?",
            documents=(_PARKING_EMPLOYEE, _PARKING_TRANSIT),
            expected_disposition="insufficient_evidence",
            forbidden_terms=("south garage",),
        ),
        _case(
            "irrelevant.internet_stipend",
            "irrelevant_matches",
            "Is there a stipend for home internet?",
            documents=(_REMOTE_STIPEND, _REMOTE_HOURS),
            expected_disposition="insufficient_evidence",
            forbidden_terms=("equipment stipend",),
        ),
        _case(
            "irrelevant.java_version",
            "irrelevant_matches",
            "Which Java version does release 4.2 require?",
            documents=(_RELEASE_41, _RELEASE_42),
            expected_disposition="insufficient_evidence",
            forbidden_terms=("java 17",),
        ),
    ]


__all__ = [
    "ABSTENTION_TEXT",
    "CATEGORIES",
    "DISPOSITIONS",
    "GRADING_FIELDS",
    "authorized_documents",
    "build_prompt",
    "cases",
]
