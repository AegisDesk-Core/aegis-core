import logging

from app.graph.state import SupportState
from app.llm import AnswerResponse, get_answer_model
from app.prompts.prompts import ANSWER_GENERATOR_PROMPT


logger = logging.getLogger(__name__)
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


def _validate_response(response: AnswerResponse, source_keys: set[tuple[str, int]]) -> bool:
    if response.needs_human or not response.answer.strip():
        return False
    if len(response.answer.split()) > MAX_ANSWER_WORDS or not response.citations:
        return False
    citations = {_source_key(item.document, item.page) for item in response.citations}
    if not citations.issubset(source_keys):
        return False
    if not response.claims or any(not claim.supported or not claim.citations for claim in response.claims):
        return False
    return all(
        _source_key(citation.document, citation.page) in source_keys
        for claim in response.claims
        for citation in claim.citations
    )


def generate_answer(state: SupportState):
    query = state.get("query", "")
    intent = state.get("intent", "other")
    docs = state.get("reranked_docs") or state.get("retrieved_docs") or []

    if not docs:
        answer = "I couldn't verify the answer from the available company information. Please connect with a support representative."
        state["answer"] = answer
        state["escalated"] = True
        state["needs_human"] = True
        return {"answer": answer, "escalated": True, "needs_human": True}

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
    for attempt in range(2):
        try:
            retry_instruction = "\nReturn every required field and cite only the labeled evidence. Do not omit claims or citations." if attempt else ""
            response = get_answer_model().invoke(prompt + retry_instruction)
        except Exception:
            logger.exception("Answer model invocation failed on attempt %d", attempt + 1)
            response = None
        if isinstance(response, AnswerResponse) and _validate_response(response, source_keys):
            break

    if not isinstance(response, AnswerResponse) or not _validate_response(response, source_keys):
        answer = "I couldn't verify that from the available company information. Please connect with a support representative."
        state.update({"answer": answer, "grounded": False, "escalated": True, "needs_human": True, "citations": []})
        return {"answer": answer, "grounded": False, "escalated": True, "needs_human": True, "citations": []}

    citations = [citation.model_dump() for citation in response.citations]
    state.update({
        "answer": response.answer,
        "grounded": True,
        "confidence": response.confidence,
        "citations": citations,
        "needs_human": response.needs_human,
    })
    return {
        "answer": response.answer,
        "grounded": True,
        "confidence": response.confidence,
        "citations": citations,
        "needs_human": response.needs_human,
    }