from contextlib import asynccontextmanager
from typing import Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.graph.graph import workflow
from app.graph.state import SupportState
from app.db.database import close_pool, open_pool
from app.db.repositories import delete_conversation
from app.services.conversation_service import (
    create_conversation,
    get_conversation,
    get_recent_messages,
    get_visible_messages,
    save_assistant_response,
    save_message,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    open_pool()
    try:
        yield
    finally:
        close_pool()


app = FastAPI(title="AI Customer Support Agent", lifespan=lifespan)
bearer_scheme = HTTPBearer(auto_error=False)

TENANT_BY_TOKEN = {
    "demo-tenant": "tenant-123",
    "customer-support": "tenant-123",
}


def database_tenant_id(tenant_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"customer-support-tenant:{tenant_id}")


def database_user_id(tenant_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"customer-support-service-user:{tenant_id}")


def database_conversation_id(conversation_id: str, tenant_id: str) -> UUID:
    try:
        return UUID(conversation_id)
    except ValueError:
        return uuid5(NAMESPACE_URL, f"customer-support-conversation:{tenant_id}:{conversation_id}")


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@app.get("/api/v1/chat/start")
async def start_chat(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Invalid or unknown tenant session.")
    token = credentials.credentials.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if token not in TENANT_BY_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or unknown tenant session.")
    return {"answer": "What is your question or problem today? I am here to help.", "needs_human": False}


@app.delete("/api/v1/conversations/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: str,
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

    try:
        deleted = delete_conversation(
            conversation_id=database_conversation_id(conversation_id, tenant_id),
            tenant_id=database_tenant_id(tenant_id),
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail="The conversation could not be deleted.") from error

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return {"deleted": True, "conversation_id": conversation_id}


@app.get("/api/v1/conversations/{conversation_id}/messages")
async def get_conversation_messages_endpoint(
    conversation_id: str,
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

    db_conversation_id = database_conversation_id(conversation_id, tenant_id)
    db_tenant_id = database_tenant_id(tenant_id)
    try:
        conversation = get_conversation(
            conversation_id=db_conversation_id,
            tenant_id=db_tenant_id,
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        messages = get_visible_messages(
            conversation_id=db_conversation_id,
            tenant_id=db_tenant_id,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail="The conversation could not be loaded.") from error

    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                **message,
                "id": str(message["id"]),
                "created_at": message["created_at"].isoformat(),
            }
            for message in messages
        ],
    }


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

    db_conversation_id = database_conversation_id(request.conversation_id, tenant_id)
    db_tenant_id = database_tenant_id(tenant_id)
    db_user_id = database_user_id(tenant_id)
    try:
        create_conversation(
            conversation_id=db_conversation_id,
            tenant_id=db_tenant_id,
            user_id=db_user_id,
        )
        user_message_id = save_message(
            conversation_id=db_conversation_id,
            tenant_id=db_tenant_id,
            content=request.message,
        )
        conversation_history = get_recent_messages(
            conversation_id=db_conversation_id,
            tenant_id=db_tenant_id,
            exclude_message_id=user_message_id,
        )
        conversation = get_conversation(
            conversation_id=db_conversation_id,
            tenant_id=db_tenant_id,
        )
        if conversation is None:
            raise LookupError("Conversation not found.")
        if conversation["memory_keywords"]:
            conversation_history.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        "Persistent conversation keywords: "
                        f"{conversation['memory_keywords']}"
                    ),
                },
            )
    except ValueError as error:
        raise HTTPException(status_code=409, detail="Conversation ID is already in use.") from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="The customer message could not be saved.") from error

    state = SupportState(
        query=request.message,
        tenant_id=tenant_id,
        conversation_id=request.conversation_id,
        conversation_history=conversation_history,
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
        citations=[],
        confidence=0.0,
        needs_human=False,
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
        "citations": result.get("citations", []),
        "sources": result.get("sources", []),
        "needs_human": bool(result.get("needs_human", result.get("escalated", False))),
        "escalated": bool(result.get("escalated", False)),
    }

    try:
        response_id = save_assistant_response(
            conversation_id=db_conversation_id,
            tenant_id=db_tenant_id,
            content=response["answer"],
            intent=response["intent"],
            confidence=response["confidence"],
            citations=response["citations"],
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="The response was generated but could not be saved.",
        ) from error

    response["response_id"] = str(response_id)
    return response
