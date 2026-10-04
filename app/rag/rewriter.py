from app.graph.state import SupportState
from app.prompts.prompts import QUERY_REWRITER_PROMPT


def rewrite_query(state: SupportState):
    query = (state.get("query") or "").strip()
    intent = state.get("intent", "other")

    stripped = query.lower()
    for token in ["hey", "hi", "hello", "can you", "could you", "please", "i want to know", "i need to know"]:
        stripped = stripped.replace(token, "")

    cleaned = " ".join(stripped.split())
    if not cleaned:
        cleaned = "support policy"

    prompt = QUERY_REWRITER_PROMPT.format(query=query, intent=intent)
    state["rewritten_query"] = cleaned
    return {"rewritten_query": cleaned, "prompt": prompt}