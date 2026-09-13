from app.graph.state import SupportState


def rerank(state: SupportState):
    query = (state.get("rewritten_query") or state.get("query") or "").lower()
    retrieved_docs = state.get("retrieved_docs") or []

    reranked = []
    for doc in retrieved_docs:
        content = str(doc.get("content", ""))
        score = float(doc.get("score", 0.0))
        if "refund" in query and "refund" in content.lower():
            score += 0.25
        if "return" in query and "return" in content.lower():
            score += 0.15
        if "shipping" in query and "shipping" in content.lower():
            score += 0.15
        if "product" in query and "product" in content.lower():
            score += 0.15
        reranked.append({"content": content, "metadata": doc.get("metadata", {}), "score": round(score, 2)})

    reranked.sort(key=lambda item: item["score"], reverse=True)
    state["reranked_docs"] = reranked[:5]
    return {"reranked_docs": reranked[:5]}