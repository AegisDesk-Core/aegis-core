from app.graph.state import SupportState


def escalation(state: SupportState):
    reason = state.get("evidence_reason") or state.get("missing_info") or "Insufficient verified company information."

    if "outside the verified company-support context" in str(reason):
        message = (
            "I can only help with questions about our company’s products, orders, shipping, "
            "and support policies. This request appears outside that scope, so I’m flagging "
            "it for a support representative."
        )
    else:
        message = (
            "I couldn't verify the answer from the available company information. "
            "I'll connect you with a support representative who can help."
        )

    state["escalated"] = True
    state["needs_human"] = True
    state["answer"] = message
    state["sources"] = []
    return {
        "answer": message,
        "escalated": True,
        "needs_human": True,
        "sources": [],
        "intent": state.get("intent", "other"),
        "confidence": float(state.get("evidence_score", 0.0)),
    }