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
        conversation_history=[],
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
        citations=[],
        confidence=0.0,
        needs_human=False,
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


def test_delete_conversation_repository_function_exists():
    from app.db.repositories import delete_conversation

    assert callable(delete_conversation)


def test_order_confirmation_question_is_not_classified_as_shipping():
    from app.agents.router import classify_intent

    state = {"query": "What are the Order Confirmation steps?"}

    assert classify_intent(state)["intent"] == "other"


def test_query_rewriter_preserves_the_question_without_topic_noise():
    from app.rag.rewriter import rewrite_query

    state = {"query": "What are the Order Confirmation steps?", "intent": "other"}

    assert rewrite_query(state)["rewritten_query"] == "what are the order confirmation steps?"


def test_lexical_retrieval_matches_contact_and_order_lifecycle_terms():
    from app.rag.rag_main import _lexical_coverage, _retrieval_score, _search_terms

    contact_chunk = "Email: support@example.com. Phone (VIP): +1 (512) 900-APEX."
    lifecycle_chunk = "Order Confirmation & Processing Lifecycle. Stage 1 — Order Received."

    assert {"email", "phone", "support", "telephone"}.issubset(
        set(_search_terms("What is the contact number and email?"))
    )
    assert _lexical_coverage(
        "What is the contact number and email?", contact_chunk
    ) == 1.0
    assert _retrieval_score(
        "What are the order confirmation steps?", lifecycle_chunk, 0.1
    ) > _retrieval_score(
        "What are the order confirmation steps?",
        "Standard Ground shipping transit time and tracking.",
        0.4,
    )
