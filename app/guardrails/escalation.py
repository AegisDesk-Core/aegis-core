from app.graph.state import SupportState


def escalation(state: SupportState):
    query = state.get("query", "")
    reason = state.get("evidence_reason") or state.get("missing_info") or "Insufficient verified company information."

    message = (
        "I couldn't verify the answer from the available company information. "
        "I'll connect you with a support representative who can help."
    )

    state["escalated"] = True
    state["answer"] = message
    state["sources"] = []
    return {
        "answer": message,
        "escalated": True,
        "sources": [],
        "intent": state.get("intent", "other"),
        "confidence": float(state.get("evidence_score", 0.0)),
    }