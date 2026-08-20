"""Provider-neutral bounded tool-loop and outcome evaluation helpers."""

from .evaluation import (
    EvalCase, EvalResult, OutcomeEvalCase, ToolEvalCase,
    evaluate_answer, evaluate_outcome, evaluate_tools, parse_sse_events,
)
from .loop import AgentEvent, AnswerStream, Tool, run_tool_loop
from .content import UNTRUSTED_CLOSE, UNTRUSTED_OPEN, safe_document_body, untrusted_document
from .runtime import AgentOutput, AgentPorts, ToolBinding, ToolOutcome, stream_agent_turn

__all__ = ["AgentEvent", "AgentOutput", "AgentPorts", "AnswerStream", "EvalCase", "EvalResult", "OutcomeEvalCase", "Tool", "ToolBinding", "ToolEvalCase", "ToolOutcome", "UNTRUSTED_CLOSE", "UNTRUSTED_OPEN", "evaluate_answer", "evaluate_outcome", "evaluate_tools", "parse_sse_events", "run_tool_loop", "safe_document_body", "stream_agent_turn", "untrusted_document"]
