from contextlib import asynccontextmanager
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.api import router as api_router
from app.auth import (
    TENANT_BY_TOKEN,
    authenticate_tenant,
    database_conversation_id,
    database_tenant_id,
    database_user_id,
)
from app.observability import emit_event, record_escalation_outcome
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
app.include_router(api_router)


@app.middleware("http")
async def log_request_telemetry(request: Request, call_next):
    request_id = str(uuid4())
    request.state.telemetry = {
        "request_id": request_id,
        "tenant_id": None,
        "user_id": None,
        "conversation_id": request.path_params.get("conversation_id"),
        "intent": None,
        "retrieval_count": 0,
        "evidence_score": None,
        "answer_latency_ms": None,
        "llm_latency_ms": None,
        "escalated": None,
        "error_type": None,
    }
    started_at = perf_counter()

    try:
        response = await call_next(request)
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        _log_request_completion(request, 500, started_at)
        raise

    response.headers["X-Request-ID"] = request_id
    status_code = response.status_code
    if status_code == 401:
        request.state.telemetry["error_type"] = "AuthenticationError"
    elif status_code >= 500 and request.state.telemetry["error_type"] is None:
        request.state.telemetry["error_type"] = "InternalServerError"
    _log_request_completion(request, status_code, started_at)
    return response


def _log_request_completion(request: Request, status_code: int, started_at: float) -> None:
    fields = dict(request.state.telemetry)
    fields.update({
        "status_code": status_code,
        "method": request.method,
        "path": getattr(request.scope.get("route"), "path", "<unmatched>"),
        "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
    })
    level = logging.WARNING if status_code == 401 or status_code >= 500 else logging.INFO
    event = "http_request_failed" if status_code == 401 or status_code >= 500 else "http_request_completed"
    emit_event(level, event, **fields)


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@app.get("/api/v1/chat/start")
async def start_chat(tenant_id: str = Depends(authenticate_tenant)):
    return {"answer": "What is your question or problem today? I am here to help.", "needs_human": False}


@app.delete("/api/v1/conversations/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: str,
    request: Request,
    tenant_id: str = Depends(authenticate_tenant),
):
    request.state.telemetry.update({
        "tenant_id": tenant_id,
        "user_id": str(database_user_id(tenant_id)),
        "conversation_id": conversation_id,
    })
    try:
        deleted = delete_conversation(
            conversation_id=database_conversation_id(conversation_id, tenant_id),
            tenant_id=database_tenant_id(tenant_id),
        )
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="The conversation could not be deleted.") from error

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return {"deleted": True, "conversation_id": conversation_id}


@app.get("/api/v1/conversations/{conversation_id}/messages")
async def get_conversation_messages_endpoint(
    conversation_id: str,
    request: Request,
    tenant_id: str = Depends(authenticate_tenant),
):
    request.state.telemetry.update({
        "tenant_id": tenant_id,
        "user_id": str(database_user_id(tenant_id)),
        "conversation_id": conversation_id,
    })
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
        request.state.telemetry["error_type"] = type(error).__name__
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
    http_request: Request,
    tenant_id: str = Depends(authenticate_tenant),
):
    db_conversation_id = database_conversation_id(request.conversation_id, tenant_id)
    db_tenant_id = database_tenant_id(tenant_id)
    db_user_id = database_user_id(tenant_id)
    telemetry = http_request.state.telemetry
    telemetry.update({
        "tenant_id": tenant_id,
        "user_id": str(db_user_id),
        "conversation_id": request.conversation_id,
    })
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
        telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=409, detail="Conversation ID is already in use.") from error
    except Exception as error:
        telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="The customer message could not be saved.") from error

    state = SupportState(
        query=request.message,
        tenant_id=tenant_id,
        conversation_id=request.conversation_id,
        request_id=telemetry["request_id"],
        user_id=str(db_user_id),
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

    answer_started_at = perf_counter()
    try:
        result = workflow.invoke(state)
    except Exception as error:
        telemetry.update({
            "error_type": type(error).__name__,
            "answer_latency_ms": round((perf_counter() - answer_started_at) * 1000, 2),
        })
        raise HTTPException(status_code=500, detail="The support request could not be processed.")
    answer_latency_ms = round((perf_counter() - answer_started_at) * 1000, 2)

    if not isinstance(result, dict):
        telemetry.update({
            "error_type": "InvalidWorkflowResponse",
            "answer_latency_ms": answer_latency_ms,
        })
        raise HTTPException(status_code=500, detail="The support workflow did not return a valid response.")

    telemetry.update({
        "intent": result.get("intent", "other"),
        "retrieval_count": len(result.get("reranked_docs") or result.get("retrieved_docs") or []),
        "evidence_score": float(result.get("evidence_score", 0.0)),
        "answer_latency_ms": answer_latency_ms,
        "llm_latency_ms": round(float(result.get("llm_latency_ms", 0.0)), 2),
        "escalated": bool(result.get("escalated", False)),
    })
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
        telemetry["error_type"] = type(error).__name__
        raise HTTPException(
            status_code=500,
            detail="The response was generated but could not be saved.",
        ) from error

    response["response_id"] = str(response_id)
    record_escalation_outcome(response["escalated"])
    return response
