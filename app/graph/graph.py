from langgraph.graph import END, START, StateGraph

from app.agents.router import check_grounding, classify_intent, route_intent
from app.final_response import format_response
from app.graph.answer import generate_answer
from app.graph.state import SupportState
from app.guardrails.escalation import escalation
from app.guardrails.evidence import check_evidence
from app.guardrails.input import validate_request
from app.rag.rag_main import retrieve
from app.rag.reranker import rerank
from app.rag.rewriter import rewrite_query

graph = StateGraph(SupportState)

graph.add_node("validate_request", validate_request)
graph.add_node("classify_intent", classify_intent)
graph.add_node("route_intent", route_intent)
graph.add_node("rewrite_query", rewrite_query)
graph.add_node("retrieve", retrieve)
graph.add_node("rerank", rerank)
graph.add_node("check_evidence", check_evidence)
graph.add_node("generate_answer", generate_answer)
graph.add_node("check_grounding", check_grounding)
graph.add_node("escalation", escalation)
graph.add_node("format_response", format_response)

graph.add_edge(START, "validate_request")
graph.add_conditional_edges(
    "validate_request",
    lambda state: "invalid" if state.get("escalated") else "valid",
    {"invalid": "escalation", "valid": "classify_intent"},
)
graph.add_edge("classify_intent", "route_intent")
graph.add_conditional_edges(
    "route_intent",
    lambda state: state.get("intent", "other"),
    {"refund": "rewrite_query", "shipping": "rewrite_query", "product": "rewrite_query", "other": "escalation"},
)
graph.add_edge("rewrite_query", "retrieve")
graph.add_edge("retrieve", "rerank")
graph.add_edge("rerank", "check_evidence")
graph.add_conditional_edges(
    "check_evidence",
    lambda state: "insufficient" if state.get("escalated") else "sufficient",
    {"insufficient": "escalation", "sufficient": "generate_answer"},
)
graph.add_edge("generate_answer", "check_grounding")
graph.add_conditional_edges(
    "check_grounding",
    lambda state: "FAIL" if not state.get("grounded", False) else "PASS",
    {"FAIL": "escalation", "PASS": "format_response"},
)
graph.add_edge("escalation", END)
graph.add_edge("format_response", END)

workflow = graph.compile()
