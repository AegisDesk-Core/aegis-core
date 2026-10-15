import re

from app.graph.state import SupportState
from app.prompts.prompts import QUERY_REWRITER_PROMPT


def rewrite_query(state: SupportState):
    query = (state.get("query") or "").strip()
    intent = state.get("intent", "other")
    history = state.get("conversation_history") or []
    history_context = "\n".join(
        f"{item.get('role', 'user')}: {item.get('content', '')[:1200]}"
        for item in history[-10:]
        if isinstance(item, dict) and item.get("content")
    )

    stripped = query.lower()
    for token in ["hey", "hi", "hello", "can you", "could you", "please", "i want to know", "i need to know"]:
        stripped = stripped.replace(token, "")

    cleaned = " ".join(stripped.split())
    if not cleaned:
        cleaned = "support policy"

    follow_up = re.search(
        r"\b(it|they|them|this|that|these|those|there|then|again|same)\b|"
        r"\b(what|how) about\b|\balso\b|\band\s+(what|how|when|where|which|does|is|can)\b",
        query.lower(),
    )
    previous_user_message = next(
        (
            item["content"][:1200]
            for item in reversed(history[-10:])
            if isinstance(item, dict)
            and item.get("role") == "user"
            and item.get("content")
        ),
        "",
    )
    if follow_up and previous_user_message:
        cleaned = f"{cleaned} {previous_user_message}"

    prompt = QUERY_REWRITER_PROMPT.format(
        query=query,
        intent=intent,
        conversation_history=history_context or "(no prior conversation)",
    )
    state["rewritten_query"] = cleaned
    return {"rewritten_query": cleaned, "prompt": prompt}