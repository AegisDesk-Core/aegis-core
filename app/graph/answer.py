import logging
from time import perf_counter

from app.graph.state import SupportState
from app.llm import AnswerResponse, get_answer_model
from app.observability import emit_event
from app.prompts.prompts import ANSWER_GENERATOR_PROMPT


MAX_ANSWER_WORDS = 120


def _source_key(document: str, page: int) -> tuple[str, int]:
    return document, int(page)


def _format_evidence(docs: list[dict]) -> tuple[str, set[tuple[str, int]]]:
    blocks = []
    source_keys = set()
    for index, doc in enumerate(docs, start=1):
        metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
        document = str(metadata.get("source", "company_policy"))
        page = int(metadata.get("page", 1))
        source_keys.add(_source_key(document, page))
        blocks.append(f"[Source {index}: document={document}; page={page}]\n{doc.get('content', '')}")
    return "\n\n".join(blocks), source_keys


def _response_validation_errors(
    response: AnswerResponse,
    source_keys: set[tuple[str, int]],
) -> list[str]:
    errors = []
    if response.needs_human or not response.answer.strip():
        errors.append("response requested human support or had an empty answer")
    if len(response.answer.split()) > MAX_ANSWER_WORDS:
        errors.append("answer exceeds the word limit")
    if not response.citations:
        errors.append("response did not cite a source")
    citations = {_source_key(item.document, item.page) for item in response.citations}
    if not citations.issubset(source_keys):
        errors.append("response cited a source not present in retrieved evidence")
    if not response.claims or any(not claim.supported or not claim.citations for claim in response.claims):
        errors.append("response claims were missing, unsupported, or uncited")
    if any(
        _source_key(citation.document, citation.page) not in source_keys
        for claim in response.claims
        for citation in claim.citations
    ):
        errors.append("a claim cited a source not present in retrieved evidence")
    return errors


def generate_answer(state: SupportState):
    query = state.get("query", "")
    intent = state.get("intent", "other")
    docs = state.get("reranked_docs") or state.get("retrieved_docs") or []

    if not docs:
        answer = "I couldn't verify the answer from the available company information. Please connect with a support representative."
        state["answer"] = answer
        state["escalated"] = True
        state["needs_human"] = True
        return {
            "answer": answer,
            "escalated": True,
            "needs_human": True,
            "llm_latency_ms": 0.0,
        }

    evidence, source_keys = _format_evidence(docs)
    state["evidence"] = evidence
    history = state.get("conversation_history") or []
    conversation_history = "\n".join(
        f"{item.get('role', 'user')}: {item.get('content', '')}"
        for item in history[-10:]
        if isinstance(item, dict) and item.get("content")
    ) or "(first message)"
    prompt = ANSWER_GENERATOR_PROMPT.format(
        query=query,
        intent=intent,
        conversation_history=conversation_history,
        evidence=evidence,
    )

    response = None
    llm_latency_ms = 0.0
    for attempt in range(2):
        llm_started_at = perf_counter()
        try:
            retry_instruction = "\nReturn every required field and cite only the labeled evidence. Do not omit claims or citations." if attempt else ""
            response = get_answer_model().invoke(prompt + retry_instruction)
        except Exception as error:
            emit_event(
                logging.ERROR,
                "llm_invocation_failed",
                request_id=state.get("request_id"),
                tenant_id=state.get("tenant_id"),
                user_id=state.get("user_id"),
                conversation_id=state.get("conversation_id"),
                error_type=type(error).__name__,
            )
            response = None
        finally:
            llm_latency_ms += (perf_counter() - llm_started_at) * 1000
        if isinstance(response, AnswerResponse):
            validation_errors = _response_validation_errors(response, source_keys)
            if not validation_errors:
                break
            emit_event(
                logging.WARNING,
                "llm_response_verification_failed",
                request_id=state.get("request_id"),
                tenant_id=state.get("tenant_id"),
                user_id=state.get("user_id"),
                conversation_id=state.get("conversation_id"),
                error_type="AnswerVerificationError",
            )
        elif response is not None:
            emit_event(
                logging.WARNING,
                "llm_unexpected_response_type",
                request_id=state.get("request_id"),
                tenant_id=state.get("tenant_id"),
                user_id=state.get("user_id"),
                conversation_id=state.get("conversation_id"),
                error_type=type(response).__name__,
            )
    state["llm_latency_ms"] = round(llm_latency_ms, 2)

    if not isinstance(response, AnswerResponse) or _response_validation_errors(response, source_keys):
        answer = "I couldn't verify that from the available company information. Please connect with a support representative."
        state.update({
            "answer": answer,
            "grounded": False,
            "escalated": True,
            "needs_human": True,
            "citations": [],
            "llm_latency_ms": round(llm_latency_ms, 2),
        })
        return {
            "answer": answer,
            "grounded": False,
            "escalated": True,
            "needs_human": True,
            "citations": [],
            "llm_latency_ms": round(llm_latency_ms, 2),
        }

    citations = [citation.model_dump() for citation in response.citations]
    state.update({
        "answer": response.answer,
        "grounded": True,
        "confidence": response.confidence,
        "citations": citations,
        "needs_human": response.needs_human,
        "llm_latency_ms": round(llm_latency_ms, 2),
    })
    return {
        "answer": response.answer,
        "grounded": True,
        "confidence": response.confidence,
        "citations": citations,
        "needs_human": response.needs_human,
        "llm_latency_ms": round(llm_latency_ms, 2),
    }