from app.graph.state import SupportState


def check_evidence(state: SupportState):
    docs = state.get("reranked_docs") or state.get("retrieved_docs") or []
    if not docs:
        state["evidence"] = ""
        state["evidence_score"] = 0.0
        state["evidence_reason"] = "No verified company documents were retrieved for this tenant and query."
        state["missing_info"] = ["relevant policy or product documentation"]
        state["escalated"] = True
        return {"evidence": "", "evidence_score": 0.0, "evidence_reason": state["evidence_reason"], "missing_info": state["missing_info"], "escalated": True}

    evidence_text = "\n\n".join(
        str(item.get("content", "")) if isinstance(item, dict) else str(item)
        for item in docs
    )

    evidence_score = 0.0
    for item in docs:
        if isinstance(item, dict):
            score = float(item.get("score", 0.0))
            evidence_score = max(evidence_score, score)

    if evidence_score < 0.45:
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