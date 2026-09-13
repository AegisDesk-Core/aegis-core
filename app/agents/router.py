from app.graph.state import SupportState
from app.prompts.prompts import INTENT_CLASSIFIER_PROMPT


def classify_intent(state: SupportState):
    query = (state.get("query") or "").lower()
    prompt = INTENT_CLASSIFIER_PROMPT.format(query=query)

    refund_keywords = [
        "refund", "return", "cancel", "cancellation", "damaged", "wrong product",
        "wrong item", "return window", "eligible", "refund amount", "send it back"
    ]
    shipping_keywords = [
        "shipping", "delivery", "track", "tracking", "ship", "arrive", "delay",
        "shipment", "courier", "delivery date", "where is my order"
    ]
    product_keywords = [
        "product", "specification", "feature", "features", "compatibility", "dimensions",
        "material", "materials", "variant", "availability", "usage", "model"
    ]

    score = {"refund": 0, "shipping": 0, "product": 0}
    for key, keywords in {"refund": refund_keywords, "shipping": shipping_keywords, "product": product_keywords}.items():
        for word in keywords:
            if word in query:
                score[key] += 1

    intent = max(score, key=score.get) if any(score.values()) else "other"
    if intent == "other" and score["refund"] == score["shipping"] == score["product"] == 0:
        intent = "other"

    state["intent"] = intent
    return {"intent": intent, "prompt": prompt}


def route_intent(state: SupportState):
    intent = state.get("intent", "other")
    if intent not in {"refund", "shipping", "product"}:
        intent = "other"
        state["escalated"] = True
    state["intent"] = intent
    return {"intent": intent}


def check_grounding(state: SupportState):
    answer = state.get("answer", "")
    evidence = state.get("evidence", "")
    grounded = bool(answer) and bool(evidence) and (
        "Not enough evidence" not in answer or answer.lower() in evidence.lower()
    )
    state["grounded"] = grounded
    if not grounded:
        state["escalated"] = True
        state["evidence_reason"] = "The answer is not fully supported by the verified evidence."
        return {"grounded": False}
    state["evidence_reason"] = "The answer is grounded in the verified evidence."
    return {"grounded": True}