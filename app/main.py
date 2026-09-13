from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.graph.graph import workflow
from app.graph.state import SupportState

app = FastAPI(title="AI Customer Support Agent")
bearer_scheme = HTTPBearer(auto_error=False)

TENANT_BY_TOKEN = {
    "demo-tenant": "tenant-123",
    "customer-support": "tenant-123",
}


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@app.post("/api/v1/ask")
async def ask_support(
    request: AskRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    token = credentials.credentials.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    tenant_id = TENANT_BY_TOKEN.get(token)
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Invalid or unknown tenant session.")

    state = SupportState(
        query=request.message,
        tenant_id=tenant_id,
        conversation_id=request.conversation_id,
        intent="",
        rewritten_query="",
        retrieved_docs=[],
        reranked_docs=[],
        evidence="",
        evidence_score=0.0,
        evidence_reason="",
        missing_info=[],
        answer="",
        sources=[],
        grounded=False,
        escalated=False,
    )

    try:
        result = workflow.invoke(state)
    except Exception:
        raise HTTPException(status_code=500, detail="The support request could not be processed.")

    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="The support workflow did not return a valid response.")

    response = {
        "answer": result.get("answer", "I couldn't verify the answer from the available company information."),
        "intent": result.get("intent", "other"),
        "confidence": float(result.get("confidence", result.get("evidence_score", 0.0))),
        "sources": result.get("sources", []),
        "escalated": bool(result.get("escalated", False)),
    }
    return response
