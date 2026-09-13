from app.graph.state import SupportState


def check_hallucination(state: SupportState):
    answer = state.get("answer", "")
    evidence = state.get("evidence", "")

    grounded = bool(answer) and bool(evidence) and answer.lower() in evidence.lower() or "not enough evidence" not in answer.lower()
    state["grounded"] = grounded
    if grounded:
        state["evidence_reason"] = "The answer is grounded in the verified evidence."
        return "PASS"
    state["evidence_reason"] = "The answer contains claims that are not supported by the verified evidence."
    state["escalated"] = True
    return "FAIL"