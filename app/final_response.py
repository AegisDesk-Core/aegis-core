from app.graph.state import SupportState


def format_response(state: SupportState):
    answer = state.get("answer") or "I couldn't verify the answer from the available company information."
    sources = [
        {
            "document": doc.get("metadata", {}).get("source", "company_policy"),
            "page": doc.get("metadata", {}).get("page", 1),
        }
        for doc in (state.get("reranked_docs") or state.get("retrieved_docs") or [])
        if isinstance(doc, dict)
    ]

    payload = {
        "answer": answer,
        "intent": state.get("intent", "other"),
        "confidence": float(state.get("evidence_score", 0.0)),
        "sources": sources,
        "escalated": bool(state.get("escalated", False)),
    }
    state["sources"] = sources
    return payload