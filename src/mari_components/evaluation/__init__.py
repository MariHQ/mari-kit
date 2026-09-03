"""Framework-neutral benchmark cases, metrics, and corpus manifests."""

from .cases import (
    EvidenceCase,
    MemoryCase,
    RetrievalCase,
    group_memory_cases,
    load_beir_cases,
    load_fever_cases,
    load_longmemeval_cases,
)
from .catalog import Corpus, CorpusCatalog, load_catalog
from .gates import GateCheck, GateMode, GateReport, MetricGate, regression_gate
from .metrics import (
    ClassificationMetrics,
    RetrievalMetrics,
    SetMetrics,
    TaskOutcome,
    TaskOutcomeComparison,
    boundary_metrics,
    classification_metrics,
    compare_task_outcomes,
    evaluate_retrieval,
    ndcg_at_k,
    reciprocal_rank,
    set_metrics,
)
from .runs import EvaluationRun
from .suites import BenchmarkSuite, BenchmarkSuiteCatalog, load_suite_catalog

__all__ = [
    "ClassificationMetrics",
    "BenchmarkSuite",
    "BenchmarkSuiteCatalog",
    "Corpus",
    "CorpusCatalog",
    "EvidenceCase",
    "EvaluationRun",
    "GateCheck",
    "GateMode",
    "GateReport",
    "MemoryCase",
    "MetricGate",
    "RetrievalMetrics",
    "RetrievalCase",
    "SetMetrics",
    "TaskOutcome",
    "TaskOutcomeComparison",
    "boundary_metrics",
    "classification_metrics",
    "compare_task_outcomes",
    "evaluate_retrieval",
    "group_memory_cases",
    "load_catalog",
    "load_beir_cases",
    "load_fever_cases",
    "load_longmemeval_cases",
    "load_suite_catalog",
    "ndcg_at_k",
    "reciprocal_rank",
    "regression_gate",
    "set_metrics",
]
