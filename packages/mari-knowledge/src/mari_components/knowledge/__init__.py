"""Strict, evidence-preserving product-knowledge recipes."""

from .answers import GroundedAnswer, answer_question, mine_answers
from .approvals import ApprovalPolicy, PolicyDecision, ReviewItem, evaluate_approval
from .decisions import extract_decisions
from .facts import FactAssessment, check_claims, extract_facts
from .glossary import harvest_glossary
from .links import (
    DEFAULT_SIMILARITY_LIMIT, DEFAULT_SIMILARITY_THRESHOLD, LinkCandidate,
    derive_links, extract_explicit_links,
)
from .refinement import RefinementEdit, refine_document
from .scoring import evidence_confidence
from .summaries import DigestSummary, DigestTopic, ImpactAssessment, assess_impact, summarize_digest
from .excerpt import excerpt
from .lifecycle import DocumentPorts, ProjectionFields
from .validation import SEVERITIES, TEMPLATE_ICONS, TONES, is_claim, iso_date, slug

__all__ = [
    "ApprovalPolicy",
    "DigestSummary",
    "DigestTopic",
    "DocumentPorts",
    "FactAssessment",
    "GroundedAnswer",
    "ImpactAssessment",
    "LinkCandidate",
    "DEFAULT_SIMILARITY_LIMIT",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "PolicyDecision",
    "ProjectionFields",
    "ReviewItem",
    "RefinementEdit",
    "answer_question",
    "assess_impact",
    "check_claims",
    "derive_links",
    "evaluate_approval",
    "excerpt",
    "evidence_confidence",
    "extract_decisions",
    "extract_explicit_links",
    "extract_facts",
    "harvest_glossary",
    "mine_answers",
    "refine_document",
    "summarize_digest",
    "SEVERITIES",
    "TEMPLATE_ICONS",
    "TONES",
    "is_claim",
    "iso_date",
    "slug",
]
