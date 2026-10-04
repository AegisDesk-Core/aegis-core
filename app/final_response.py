from app.graph.state import SupportState


def format_response(state: SupportState):
    answer = state.get("answer") or "I couldn't verify the answer from the available company information."
    sources = state.get("citations") or []

    payload = {
        "answer": answer,
        "intent": state.get("intent", "other"),
        "confidence": float(state.get("confidence", state.get("evidence_score", 0.0))),
        "citations": sources,
        "sources": sources,
        "needs_human": bool(state.get("needs_human", state.get("escalated", False))),
        "escalated": bool(state.get("escalated", False)),
    }
    state["sources"] = sources
    return payload