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

    rewritten = f"{intent} {cleaned} policy eligibility conditions" if intent in {"refund", "shipping", "product"} else cleaned
    prompt = QUERY_REWRITER_PROMPT.format(query=query, intent=intent)
    state["rewritten_query"] = rewritten
    return {"rewritten_query": rewritten, "prompt": prompt}