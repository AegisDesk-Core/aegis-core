import re

from app.graph.state import SupportState


def validate_request(state: SupportState):
    query = (state.get("query") or "").strip()

    if not query:
        state["escalated"] = True
        return {"escalated": True, "answer": "I couldn't verify the answer from the available company information."}

    lowered = query.lower()
    blocked_patterns = [
        "ignore previous instructions",
        "reveal system prompt",
        "system prompt",
        "internal company data",
        "another tenant",
        "show me your prompt",
        "bypass policy",
        "access other tenant",
        "dump your instructions",
    ]

    if any(pattern in lowered for pattern in blocked_patterns):
        state["escalated"] = True
        return {"escalated": True, "answer": "I couldn't verify the answer from the available company information."}

    if len(query) < 3 or len(query.split()) > 500:
        state["escalated"] = True
        return {"escalated": True, "answer": "I couldn't verify the answer from the available company information."}

    if re.search(r"(?:\b(?:api[_ -]?key|token|secret|password)\b.*\b(?:show|reveal|leak)\b)|(?:prompt\s*injection)", lowered):
        state["escalated"] = True
        return {"escalated": True, "answer": "I couldn't verify the answer from the available company information."}

    state["query"] = query
    state["escalated"] = False
    return {"query": query, "escalated": False}