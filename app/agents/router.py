import re

from app.graph.state import SupportState
from app.prompts.prompts import INTENT_CLASSIFIER_PROMPT


INTRODUCTION_PATTERN = re.compile(
    r"\b(?:i['’]?m|i am|my name is|this is)\s+([a-z][a-z'-]{0,39})\b",
    re.IGNORECASE,
)
CAPABILITY_QUESTION_PATTERN = re.compile(
    r"\bhow can (?:you|this assistant) help\b|\bwhat can (?:you|this assistant) help\b",
    re.IGNORECASE,
)
GREETING_PATTERN = re.compile(
    r"^\s*(?:(?:hi|hello|hey|good morning|good afternoon|good evening)"
    r"\b[\s,.!'-]*)+$",
    re.IGNORECASE,
)


def classify_intent(state: SupportState):
    query = (state.get("query") or "").lower()
    prompt = INTENT_CLASSIFIER_PROMPT.format(query=query)

    refund_keywords = [
        "refund", "return", "cancel", "cancellation", "damaged", "wrong product",
        "wrong item", "return window", "eligible", "refund amount", "send it back",
        "replace", "replacement", "not working", "broken", "defective"
    ]
    shipping_keywords = [
        "shipping", "delivery", "track", "tracking", "ship", "arrive", "delay",
        "shipment", "courier", "delivery date", "where is my order",
        "home", "how many days", "how long", "reach me", "deliver"
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
    if not any(score.values()) and (
        INTRODUCTION_PATTERN.search(query)
        or GREETING_PATTERN.fullmatch(query)
        or CAPABILITY_QUESTION_PATTERN.search(query)
    ):
        intent = "small_talk"
    if intent == "other" and score["refund"] == score["shipping"] == score["product"] == 0:
        intent = "other"

    state["intent"] = intent
    return {"intent": intent, "prompt": prompt}


def route_intent(state: SupportState):
    intent = state.get("intent", "other")
    if intent not in {"refund", "shipping", "product", "other", "small_talk"}:
        intent = "other"
    state["intent"] = intent
    return {"intent": intent}


def respond_to_small_talk(state: SupportState):
    query = state.get("query", "")
    introduction = INTRODUCTION_PATTERN.search(query)
    name = introduction.group(1).strip().capitalize() if introduction else None
    greeting = f"Hi, {name}! Nice to meet you." if name else "Hi! Nice to meet you."
    answer = (
        f"{greeting} I can help you understand our return and refund policies, "
        "shipping and delivery information, and product details such as features "
        "or compatibility. I answer from the company information available to me, "
        "and I can flag questions for a support representative when that information "
        "does not cover what you need. I do not have access to live order or account "
        "details unless they are provided here. What would you like help with?"
    )
    state.update({
        "answer": answer,
        "intent": "small_talk",
        "confidence": 1.0,
        "needs_human": False,
        "grounded": True,
        "escalated": False,
        "citations": [],
        "sources": [],
    })
    return {
        "answer": answer,
        "intent": "small_talk",
        "confidence": 1.0,
        "needs_human": False,
        "grounded": True,
        "escalated": False,
        "citations": [],
        "sources": [],
    }


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