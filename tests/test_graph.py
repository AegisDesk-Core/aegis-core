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
        "respond_to_small_talk",
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


def test_self_introduction_gets_a_welcome_without_retrieval():
    result = workflow.invoke({
        "query": "im aman, how can you help me",
        "tenant_id": "tenant-123",
        "conversation_id": "conv_123",
        "conversation_history": [],
        "intent": "",
        "rewritten_query": "",
        "retrieved_docs": [],
        "reranked_docs": [],
        "evidence": "",
        "evidence_score": 0.0,
        "evidence_reason": "",
        "missing_info": [],
        "answer": "",
        "sources": [],
        "citations": [],
        "confidence": 0.0,
        "needs_human": False,
        "grounded": False,
        "escalated": False,
    })

    assert result["intent"] == "small_talk"
    assert "Aman" in result["answer"]
    assert "return and refund policies" in result["answer"]
    assert "shipping and delivery information" in result["answer"]
    assert "do not have access to live order or account details" in result["answer"]
    assert result["needs_human"] is False
    assert result["escalated"] is False


def test_capability_question_without_introduction_gets_assistant_scope():
    from app.agents.router import classify_intent

    assert classify_intent({"query": "How can you help me?"})["intent"] == "small_talk"


def test_support_question_with_greeting_still_uses_support_intent():
    from app.agents.router import classify_intent

    assert classify_intent({"query": "Hi, can I return my laptop?"})["intent"] == "refund"


def test_out_of_context_question_does_not_get_an_answer_from_unrelated_evidence():
    from app.guardrails.evidence import check_evidence
    from app.guardrails.escalation import escalation

    state = {
        "query": "Who won the football match yesterday?",
        "rewritten_query": "who won football match yesterday",
        "retrieved_docs": [],
        "reranked_docs": [
            {
                "content": "Our return policy allows eligible products to be returned within 30 days.",
                "score": 0.9,
            }
        ],
        "evidence": "",
        "evidence_score": 0.0,
        "evidence_reason": "",
        "missing_info": [],
        "escalated": False,
        "intent": "other",
        "needs_human": False,
        "answer": "",
        "sources": [],
    }

    result = check_evidence(state)
    response = escalation(state)

    assert result["escalated"] is True
    assert state["needs_human"] is True
    assert response["needs_human"] is True
    assert "outside that scope" in response["answer"]
    assert "flagging" in response["answer"]


def test_relevant_company_question_passes_the_context_check():
    from app.guardrails.evidence import check_evidence

    state = {
        "query": "Can I return this product?",
        "rewritten_query": "can i return this product",
        "retrieved_docs": [],
        "reranked_docs": [
            {
                "content": "Products can be returned within 30 days of purchase.",
                "score": 0.8,
            }
        ],
        "evidence": "",
        "evidence_score": 0.0,
        "evidence_reason": "",
        "missing_info": [],
        "escalated": False,
    }

    result = check_evidence(state)

    assert result["escalated"] is False
    assert result["evidence_score"] == 0.8


def test_query_rewriter_preserves_the_question_without_topic_noise():
    from app.rag.rewriter import rewrite_query

    state = {"query": "What are the Order Confirmation steps?", "intent": "other"}

    assert rewrite_query(state)["rewritten_query"] == "what are the order confirmation steps?"


def test_query_rewriter_uses_recent_context_for_follow_up_questions():
    from app.rag.rewriter import rewrite_query

    state = {
        "query": "What about its delivery time?",
        "intent": "shipping",
        "conversation_history": [
            {"role": "user", "content": "How do I return order 12345?"},
            {"role": "assistant", "content": "Use the return portal."},
        ],
    }

    result = rewrite_query(state)

    assert "How do I return order 12345?" in result["rewritten_query"]
    assert "How do I return order 12345?" in result["prompt"]


def test_recent_conversation_context_is_limited_to_nine_messages(monkeypatch):
    from app.services import conversation_service

    class FakeResult:
        def __init__(self, limit):
            self.limit = limit

        def fetchall(self):
            return [
                (index, "user", f"message {index}", None)
                for index in range(9, 9 - self.limit, -1)
            ]

    class FakeConnection:
        query = ""
        parameters = ()

        def execute(self, query, parameters):
            self.query = query
            self.parameters = parameters
            return FakeResult(parameters[-1])

    connection = FakeConnection()

    class ConnectionContext:
        def __enter__(self):
            return connection

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(
        conversation_service,
        "get_connection",
        lambda: ConnectionContext(),
    )

    messages = conversation_service.get_recent_messages(
        conversation_id="conversation-id",
        tenant_id="tenant-id",
        limit=100,
    )

    assert len(messages) == 9
    assert messages[0]["content"] == "message 1"
    assert "LEFT(content, %s)" in connection.query
    assert connection.parameters[-1] == 9


def test_conversation_keyword_memory_keeps_identifiers_with_a_fixed_budget():
    from app.services.conversation_service import _updated_memory_keywords

    memory = _updated_memory_keywords(
        "older-topic",
        "Order 12345 is linked to customer@example.com and needs a refund.",
    )

    assert "12345" in memory
    assert "customer@example.com" in memory
    assert "older-topic" in memory
    assert len(memory) <= 1200


def test_answer_model_schema_requires_citations_and_supported_claims():
    from pydantic import ValidationError

    from app.llm import AnswerResponse, Citation, SupportedClaim

    schema = AnswerResponse.model_json_schema()
    assert {"answer", "confidence", "citations", "claims"}.issubset(
        schema["required"]
    )
    assert "citations" in SupportedClaim.model_json_schema()["required"]

    citation = Citation(document="policy.pdf", page=1)
    answer = AnswerResponse(
        answer="The return window is 30 days.",
        confidence=0.9,
        citations=[citation],
        claims=[
            SupportedClaim(
                claim="The return window is 30 days.",
                supported=True,
                citations=[citation],
            )
        ],
    )
    assert answer.answer

    try:
        AnswerResponse(answer="The return window is 30 days.", confidence=0.9)
    except ValidationError:
        pass
    else:
        raise AssertionError("Responses without citations and claims must be rejected.")


def test_generated_answer_passes_verification_when_sources_match(monkeypatch):
    from app.graph import answer as answer_module
    from app.llm import AnswerResponse, Citation, SupportedClaim

    citation = Citation(document="policy.pdf", page=1)
    expected = AnswerResponse(
        answer="The return window is 30 days.",
        confidence=0.9,
        citations=[citation],
        claims=[
            SupportedClaim(
                claim="The return window is 30 days.",
                supported=True,
                citations=[citation],
            )
        ],
    )

    class FakeModel:
        def invoke(self, _prompt):
            return expected

    monkeypatch.setattr(answer_module, "get_answer_model", lambda: FakeModel())
    state = {
        "query": "How long is the return window?",
        "intent": "refund",
        "reranked_docs": [
            {
                "content": "The return window is 30 days.",
                "metadata": {"source": "policy.pdf", "page": 1},
            }
        ],
        "conversation_history": [],
    }

    result = answer_module.generate_answer(state)

    assert result["answer"] == expected.answer
    assert result["grounded"] is True
    assert result["citations"] == [{"document": "policy.pdf", "page": 1}]
    assert result["llm_latency_ms"] >= 0


def test_google_answer_model_uses_native_structured_response(monkeypatch):
    from types import SimpleNamespace

    from app import llm

    expected = llm.AnswerResponse(
        answer="The return window is 30 days.",
        confidence=0.9,
        citations=[llm.Citation(document="policy.pdf", page=1)],
        claims=[
            llm.SupportedClaim(
                claim="The return window is 30 days.",
                supported=True,
                citations=[llm.Citation(document="policy.pdf", page=1)],
            )
        ],
    )
    calls = {}

    class FakeChat:
        def send_message(self, prompt):
            calls["prompt"] = prompt
            return SimpleNamespace(parsed=expected, text=None)

    class FakeChats:
        def create(self, *, model, config):
            calls["model"] = model
            calls["config"] = config
            return FakeChat()

    class FakeClient:
        chats = FakeChats()

    adapter = llm._GoogleAnswerModel.__new__(llm._GoogleAnswerModel)
    adapter.client = FakeClient()
    adapter.model_name = "test-model"

    result = adapter.invoke("Answer from this evidence.")

    assert result is expected
    assert calls["config"].response_schema is llm.AnswerResponse
    assert calls["model"] == "test-model"


def test_google_answer_model_default_uses_gemini_35_flash_lite(monkeypatch):
    from app import llm
    import app.config

    selected = {}

    class FakeGoogleModel:
        def __init__(self, model_name, _api_key):
            selected["model_name"] = model_name

    monkeypatch.setattr(
        app.config,
        "get_env",
        lambda key: "test-key" if key == "GEMINI_API_KEY" else None,
    )
    monkeypatch.setattr(llm, "_GoogleAnswerModel", FakeGoogleModel)

    llm.get_answer_model()

    assert selected["model_name"] == "gemini-3.5-flash-lite"


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
