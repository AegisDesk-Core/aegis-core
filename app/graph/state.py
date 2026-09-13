from typing import List, TypedDict


class SupportState(TypedDict):
    query: str
    tenant_id: str
    conversation_id: str

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

    grounded: bool
    escalated: bool