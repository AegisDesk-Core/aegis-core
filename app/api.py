from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.auth import (
    authenticate_admin,
    authenticate_tenant,
    database_conversation_id,
    database_tenant_id,
    database_user_id,
)
from app.db.database import get_connection
from app.observability import escalation_monitor_state
from app.services.document_service import (
    DOCUMENTS_DIR,
    MAX_DOCUMENT_BYTES,
    DocumentUploadError,
    process_document_job,
    save_document_upload,
)
from app.services.conversation_service import get_conversation


router = APIRouter(prefix="/api/v1")


class FeedbackRequest(BaseModel):
    conversation_id: UUID
    message_id: UUID
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


def _set_request_tenant(request: Request, tenant_id: str) -> UUID:
    request.state.telemetry.update({
        "tenant_id": tenant_id,
        "user_id": str(database_user_id(tenant_id)),
    })
    return database_tenant_id(tenant_id)


def _document_response(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "filename": row[1],
        "status": row[2],
        "created_at": row[3].isoformat(),
        "updated_at": row[4].isoformat(),
    }


def _stored_document_path(storage_path: str) -> Path:
    root = DOCUMENTS_DIR.resolve()
    path = Path(storage_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError("Document storage path is outside the document directory.") from error
    return path


@router.post("/documents", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    tenant_id: str = Depends(authenticate_tenant),
):
    _set_request_tenant(request, tenant_id)
    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    try:
        row, path, _duplicate = save_document_upload(
            filename=file.filename,
            content=content,
            tenant_id=tenant_id,
        )
    except DocumentUploadError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="The document could not be saved.") from error

    if path is not None:
        background_tasks.add_task(process_document_job, path, tenant_id, row[0])
    return {
        "document_id": str(row[0]),
        "filename": row[1],
        "status": row[2],
    }


@router.get("/documents")
async def list_documents(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tenant_id: str = Depends(authenticate_tenant),
):
    tenant_uuid = _set_request_tenant(request, tenant_id)
    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, filename, status, created_at, updated_at
                FROM documents
                WHERE tenant_id = %s AND status != 'deleted'
                ORDER BY created_at DESC, id
                LIMIT %s OFFSET %s
                """,
                (tenant_uuid, limit, offset),
            ).fetchall()
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="Documents could not be loaded.") from error
    return {"documents": [_document_response(row) for row in rows], "limit": limit, "offset": offset}


@router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID,
    request: Request,
    tenant_id: str = Depends(authenticate_tenant),
):
    tenant_uuid = _set_request_tenant(request, tenant_id)
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, filename, status, created_at, updated_at
                FROM documents
                WHERE id = %s AND tenant_id = %s AND status != 'deleted'
                """,
                (document_id, tenant_uuid),
            ).fetchone()
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="The document could not be loaded.") from error
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _document_response(row)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    request: Request,
    tenant_id: str = Depends(authenticate_tenant),
):
    tenant_uuid = _set_request_tenant(request, tenant_id)
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                UPDATE documents
                SET status = 'deleted', deleted_at = now(), updated_at = now()
                WHERE id = %s AND tenant_id = %s AND status != 'deleted'
                RETURNING storage_path
                """,
                (document_id, tenant_uuid),
            ).fetchone()
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="The document could not be deleted.") from error
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        path = _stored_document_path(row[0])
        path.unlink(missing_ok=True)
    except (OSError, ValueError) as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="Document metadata was deleted but its file could not be removed.") from error
    return {"deleted": True, "document_id": str(document_id)}


@router.post("/documents/{document_id}/reindex", status_code=202)
async def reindex_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    tenant_id: str = Depends(authenticate_tenant),
):
    tenant_uuid = _set_request_tenant(request, tenant_id)
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT storage_path, status
                FROM documents
                WHERE id = %s AND tenant_id = %s AND status != 'deleted'
                """,
                (document_id, tenant_uuid),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Document not found.")
            if row[1] in {"pending", "processing"}:
                raise HTTPException(status_code=409, detail="The document is already queued or being indexed.")
            try:
                path = _stored_document_path(row[0])
            except ValueError as error:
                raise HTTPException(status_code=500, detail="Invalid document storage path.") from error
            if not path.is_file():
                raise HTTPException(status_code=409, detail="The stored PDF is missing and cannot be reindexed.")
            updated_row = connection.execute(
                """
                UPDATE documents SET status = 'pending', updated_at = now()
                WHERE id = %s AND tenant_id = %s AND status IN ('ready', 'failed')
                RETURNING id
                """,
                (document_id, tenant_uuid),
            ).fetchone()
            if updated_row is None:
                raise HTTPException(status_code=409, detail="The document status changed before it could be reindexed.")
    except HTTPException:
        raise
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="The document could not be queued for reindexing.") from error
    background_tasks.add_task(process_document_job, path, tenant_id, document_id)
    return {"document_id": str(document_id), "status": "pending"}


@router.get("/conversations")
async def list_conversations(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tenant_id: str = Depends(authenticate_tenant),
):
    tenant_uuid = _set_request_tenant(request, tenant_id)
    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, status, created_at, updated_at
                FROM conversations
                WHERE tenant_id = %s AND status != 'deleted'
                ORDER BY updated_at DESC, id
                LIMIT %s OFFSET %s
                """,
                (tenant_uuid, limit, offset),
            ).fetchall()
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="Conversations could not be loaded.") from error
    return {
        "conversations": [
            {
                "id": str(row[0]),
                "status": row[1],
                "created_at": row[2].isoformat(),
                "updated_at": row[3].isoformat(),
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation_endpoint(
    conversation_id: str,
    request: Request,
    tenant_id: str = Depends(authenticate_tenant),
):
    tenant_uuid = _set_request_tenant(request, tenant_id)
    request.state.telemetry["conversation_id"] = conversation_id
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, status, created_at, updated_at
                FROM conversations
                WHERE id = %s AND tenant_id = %s AND status != 'deleted'
                """,
                (database_conversation_id(conversation_id, tenant_id), tenant_uuid),
            ).fetchone()
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="The conversation could not be loaded.") from error
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {
        "id": str(row[0]),
        "status": row[1],
        "created_at": row[2].isoformat(),
        "updated_at": row[3].isoformat(),
    }


@router.post("/feedback", status_code=201)
async def submit_feedback(
    feedback: FeedbackRequest,
    request: Request,
    tenant_id: str = Depends(authenticate_tenant),
):
    tenant_uuid = _set_request_tenant(request, tenant_id)
    request.state.telemetry["conversation_id"] = str(feedback.conversation_id)
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                INSERT INTO feedback (tenant_id, conversation_id, message_id, rating, comment)
                SELECT %s, c.id, m.id, %s, %s
                FROM conversations c
                JOIN messages m
                    ON m.conversation_id = c.id AND m.tenant_id = c.tenant_id
                WHERE c.id = %s AND c.tenant_id = %s
                    AND c.status != 'deleted'
                    AND m.id = %s AND m.role = 'assistant'
                RETURNING id, created_at
                """,
                (
                    tenant_uuid,
                    feedback.rating,
                    feedback.comment,
                    feedback.conversation_id,
                    tenant_uuid,
                    feedback.message_id,
                ),
            ).fetchone()
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="Feedback could not be saved.") from error
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation or assistant message not found.")
    return {"id": str(row[0]), "created_at": row[1].isoformat()}


@router.get("/admin/metrics", dependencies=[Depends(authenticate_admin)])
async def admin_metrics(request: Request):
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM tenants WHERE status = 'active'),
                    (SELECT COUNT(*) FROM documents WHERE status != 'deleted'),
                    (SELECT COUNT(*) FROM conversations WHERE status != 'deleted'),
                    (SELECT COUNT(*) FROM messages),
                    (SELECT COUNT(*) FROM feedback)
                """
            ).fetchone()
    except Exception as error:
        request.state.telemetry["error_type"] = type(error).__name__
        raise HTTPException(status_code=500, detail="Admin metrics could not be loaded.") from error
    sample_count, escalation_rate = escalation_monitor_state()
    return {
        "active_tenants": row[0],
        "documents": row[1],
        "conversations": row[2],
        "messages": row[3],
        "feedback": row[4],
        "escalations": {"sample_count": sample_count, "rate": escalation_rate},
    }
