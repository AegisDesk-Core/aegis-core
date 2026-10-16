import logging

from app.graph.state import SupportState
from app.observability import emit_event
from app.rag.rag_main import _lexical_coverage


MIN_EVIDENCE_SCORE = 0.25
MIN_LEXICAL_COVERAGE = 0.15
OUT_OF_SCOPE_REASON = (
    "The request is outside the verified company-support context or has no direct "
    "match in the available company documents."
)


def check_evidence(state: SupportState):
    docs = state.get("reranked_docs") or state.get("retrieved_docs") or []
    if not docs:
        state["evidence"] = ""
        state["evidence_score"] = 0.0
        state["evidence_reason"] = "No verified company documents were retrieved for this tenant and query."
        state["missing_info"] = ["relevant policy or product documentation"]
        state["escalated"] = True
        emit_event(
            logging.WARNING,
            "low_evidence_score",
            request_id=state.get("request_id"),
            tenant_id=state.get("tenant_id"),
            user_id=state.get("user_id"),
            conversation_id=state.get("conversation_id"),
            intent=state.get("intent"),
            retrieval_count=0,
            evidence_score=0.0,
            escalated=True,
        )
        return {"evidence": "", "evidence_score": 0.0, "evidence_reason": state["evidence_reason"], "missing_info": state["missing_info"], "escalated": True}

    evidence_text = "\n\n".join(
        str(item.get("content", "")) if isinstance(item, dict) else str(item)
        for item in docs
    )

    evidence_score = 0.0
    query = state.get("rewritten_query") or state.get("query") or ""
    lexical_coverage = 0.0
    for item in docs:
        if isinstance(item, dict):
            score = float(item.get("score", 0.0))
            evidence_score = max(evidence_score, score)
            lexical_coverage = max(
                lexical_coverage,
                _lexical_coverage(query, str(item.get("content", ""))),
            )

    if evidence_score < MIN_EVIDENCE_SCORE:
        emit_event(
            logging.WARNING,
            "low_evidence_score",
            request_id=state.get("request_id"),
            tenant_id=state.get("tenant_id"),
            user_id=state.get("user_id"),
            conversation_id=state.get("conversation_id"),
            intent=state.get("intent"),
            retrieval_count=len(docs),
            evidence_score=evidence_score,
            escalated=True,
        )

    if lexical_coverage < MIN_LEXICAL_COVERAGE:
        state["evidence"] = evidence_text
        state["evidence_score"] = evidence_score
        state["evidence_reason"] = OUT_OF_SCOPE_REASON
        state["missing_info"] = ["a directly related company support topic"]
        state["escalated"] = True
        return {
            "evidence": evidence_text,
            "evidence_score": evidence_score,
            "evidence_reason": OUT_OF_SCOPE_REASON,
            "missing_info": state["missing_info"],
            "escalated": True,
        }

    if evidence_score < MIN_EVIDENCE_SCORE:
        state["evidence"] = evidence_text
        state["evidence_score"] = evidence_score
        state["evidence_reason"] = "Retrieved documents were not specific or directly relevant enough to answer safely."
        state["missing_info"] = ["relevant policy or product details"]
        state["escalated"] = True
        return {"evidence": evidence_text, "evidence_score": evidence_score, "evidence_reason": state["evidence_reason"], "missing_info": state["missing_info"], "escalated": True}

    state["evidence"] = evidence_text
    state["evidence_score"] = evidence_score
    state["evidence_reason"] = "The retrieved documents directly address the customer's request and conditions."
    state["missing_info"] = []
    state["escalated"] = False
    return {"evidence": evidence_text, "evidence_score": evidence_score, "evidence_reason": state["evidence_reason"], "missing_info": [], "escalated": False}