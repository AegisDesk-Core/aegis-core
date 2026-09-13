import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.graph.graph import workflow
from app.graph.state import SupportState


def test_support_state_contract():
    state = SupportState(
        query="Can I return my laptop after 20 days?",
        tenant_id="tenant-123",
        conversation_id="conv_123",
        intent="",
        rewritten_query="",
        retrieved_docs=[],
        reranked_docs=[],
        evidence="",
        evidence_score=0.0,
        evidence_reason="",
        missing_info=[],
        answer="",
        sources=[],
        grounded=False,
        escalated=False,
    )

    assert state["query"]
    assert "retrieved_docs" in state
    assert "reranked_docs" in state
    assert "evidence_reason" in state
    assert "missing_info" in state
    assert "sources" in state
    assert "grounded" in state
    assert "escalated" in state


def test_graph_has_expected_nodes():
    graph = workflow.get_graph()
    expected = {
        "validate_request",
        "classify_intent",
        "route_intent",
        "rewrite_query",
        "retrieve",
        "rerank",
        "check_evidence",
        "generate_answer",
        "check_grounding",
        "escalation",
        "format_response",
        "__start__",
    }

    actual = {node for node in graph.nodes}
    assert expected.issubset(actual)
