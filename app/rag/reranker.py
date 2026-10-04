from app.graph.state import SupportState
from app.rag.rag_main import _lexical_coverage


def rerank(state: SupportState):
    query = (state.get("rewritten_query") or state.get("query") or "").lower()
    retrieved_docs = state.get("retrieved_docs") or []

    reranked = []
    for doc in retrieved_docs:
        content = str(doc.get("content", ""))
        score = float(doc.get("score", 0.0))
        lexical_score = _lexical_coverage(query, content)
        reranked.append({
            "content": content,
            "metadata": doc.get("metadata", {}),
            "score": round(score + 0.15 * lexical_score, 4),
        })

    reranked.sort(key=lambda item: item["score"], reverse=True)
    state["reranked_docs"] = reranked[:5]
    return {"reranked_docs": reranked[:5]}