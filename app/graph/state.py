from typing import List, NotRequired, TypedDict


class SupportState(TypedDict):
    query: str
    tenant_id: str
    conversation_id: str
    request_id: NotRequired[str]
    user_id: NotRequired[str]
    conversation_history: list
    llm_latency_ms: NotRequired[float]

    intent: str
    rewritten_query: str

    retrieved_docs: list
    reranked_docs: list

    evidence: str
    evidence_score: float
    evidence_reason: str
    missing_info: List[str]

    answer: str
    sources: list
    citations: list
    confidence: float
    needs_human: bool

    grounded: bool
    escalated: bool