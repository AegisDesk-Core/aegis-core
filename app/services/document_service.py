import hashlib
import logging
import math
import re
from os import environ
from pathlib import Path
from time import perf_counter, sleep
from typing import Any
from uuid import UUID, uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.auth import database_tenant_id
from app.config import get_env
from app.db.database import get_connection
from app.observability import emit_event, slow_document_processing_threshold_ms

try:
    from langchain_mistralai import MistralAIEmbeddings
except Exception:
    MistralAIEmbeddings = None


DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "data" / "documents"
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
MAX_INDEX_ATTEMPTS = 3


class DocumentUploadError(ValueError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class LocalHashEmbeddings(Embeddings):
    """Deterministic local embeddings for offline indexing and retrieval."""

    size = 1536

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.size
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.size
            sign = 1.0 if digest[4] % 2 else -1.0
            vector[index] += sign
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def get_embeddings():
    provider = (get_env("EMBEDDING_PROVIDER") or "local").strip().lower()

    if provider == "mistral":
        api_key = get_env("MISTRAL_API_KEY")
        if api_key:
            environ["MISTRAL_API_KEY"] = api_key
        if MistralAIEmbeddings is not None:
            try:
                return MistralAIEmbeddings(model="mistral-embed")
            except Exception:
                pass

    return LocalHashEmbeddings()


def validate_document_upload(filename: str | None, content: bytes) -> tuple[str, str]:
    safe_filename = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not safe_filename or Path(safe_filename).suffix.lower() != ".pdf":
        raise DocumentUploadError("Only PDF documents are supported.", 415)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise DocumentUploadError("PDF exceeds the 20 MB upload limit.", 413)
    if not content.startswith(b"%PDF-"):
        raise DocumentUploadError("Uploaded file is not a valid PDF.", 415)
    return safe_filename, hashlib.sha256(content).hexdigest()


def save_document_upload(
    *,
    filename: str | None,
    content: bytes,
    tenant_id: str,
) -> tuple[tuple[Any, ...], Path | None, bool]:
    safe_filename, content_hash = validate_document_upload(filename, content)
    tenant_uuid = database_tenant_id(tenant_id)
    tenant_directory = (DOCUMENTS_DIR / tenant_id).resolve()
    try:
        tenant_directory.relative_to(DOCUMENTS_DIR.resolve())
    except ValueError as error:
        raise DocumentUploadError("Invalid tenant document storage path.", 400) from error

    tenant_directory.mkdir(parents=True, exist_ok=True)
    document_id = uuid4()
    path = tenant_directory / f"{document_id}.pdf"
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO tenants (id, name)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (tenant_uuid, tenant_id),
            )
            existing = connection.execute(
                """
                SELECT id, filename, status, created_at, updated_at
                FROM documents
                WHERE tenant_id = %s AND content_hash = %s
                """,
                (tenant_uuid, content_hash),
            ).fetchone()
            if existing is not None:
                return existing, None, True

            path.write_bytes(content)
            row = connection.execute(
                """
                INSERT INTO documents
                    (id, tenant_id, filename, storage_path, content_hash, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                ON CONFLICT (tenant_id, content_hash) DO NOTHING
                RETURNING id, filename, status, created_at, updated_at
                """,
                (document_id, tenant_uuid, safe_filename, str(path), content_hash),
            ).fetchone()
            if row is not None:
                return row, path, False

            existing = connection.execute(
                """
                SELECT id, filename, status, created_at, updated_at
                FROM documents
                WHERE tenant_id = %s AND content_hash = %s
                """,
                (tenant_uuid, content_hash),
            ).fetchone()
            if existing is None:
                raise RuntimeError("Document upload conflicted without an existing document.")
            path.unlink(missing_ok=True)
            return existing, None, True
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _extract_pdf_chunks(pdf_path: Path, tenant_id: str) -> list[Document]:
    reader = PdfReader(str(pdf_path))
    pages = [
        Document(
            page_content=text,
            metadata={"source": pdf_path.name, "page": page_number, "tenant_id": tenant_id},
        )
        for page_number, page in enumerate(reader.pages, start=1)
        if (text := page.extract_text())
    ]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_documents(pages)


def index_document(pdf_path: Path, *, tenant_id: str, document_id: UUID) -> int:
    chunks = _extract_pdf_chunks(pdf_path, tenant_id)
    if not chunks:
        raise ValueError("The uploaded PDF contains no indexable text.")

    embeddings = get_embeddings()
    vectors = embeddings.embed_documents([chunk.page_content for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("Embedding provider returned a mismatched number of vectors.")

    tenant_uuid = database_tenant_id(tenant_id)
    document_hash = _content_hash_for_path(pdf_path)
    with get_connection() as connection:
        document_row = connection.execute(
            """
            SELECT id
            FROM documents
            WHERE id = %s AND tenant_id = %s AND status = 'processing'
            FOR UPDATE
            """,
            (document_id, tenant_uuid),
        ).fetchone()
        if document_row is None:
            raise LookupError("Document is no longer available for indexing.")

        connection.execute(
            "DELETE FROM document_chunks WHERE document_id = %s AND tenant_id = %s",
            (document_id, tenant_uuid),
        )
        for chunk_number, (chunk, vector) in enumerate(zip(chunks, vectors), start=1):
            connection.execute(
                """
                INSERT INTO document_chunks
                    (document_id, tenant_id, chunk_number, content, page_number, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    document_id,
                    tenant_uuid,
                    chunk_number,
                    chunk.page_content,
                    int(chunk.metadata.get("page", 1)),
                    vector,
                ),
            )
        updated = connection.execute(
            """
            UPDATE documents
            SET content_hash = %s, status = 'ready', updated_at = now(),
                embedding_model = %s, chunk_size = %s, chunk_overlap = %s
            WHERE id = %s AND tenant_id = %s AND status = 'processing'
            RETURNING id
            """,
            (
                document_hash,
                (get_env("EMBEDDING_PROVIDER") or "local").strip().lower(),
                CHUNK_SIZE,
                CHUNK_OVERLAP,
                document_id,
                tenant_uuid,
            ),
        ).fetchone()
        if updated is None:
            raise LookupError("Document changed while its chunks were being saved.")
    return len(chunks)


def _content_hash_for_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as document:
        for block in iter(lambda: document.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def process_document_job(
    path: Path,
    tenant_id: str,
    document_id: UUID,
    *,
    max_attempts: int = MAX_INDEX_ATTEMPTS,
) -> None:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one.")

    tenant_uuid = database_tenant_id(tenant_id)
    try:
        with get_connection() as connection:
            claimed = connection.execute(
                """
                UPDATE documents SET status = 'processing', updated_at = now()
                WHERE id = %s AND tenant_id = %s AND status = 'pending'
                RETURNING id
                """,
                (document_id, tenant_uuid),
            ).fetchone()
        if claimed is None:
            return
    except Exception as error:
        _mark_job_failed(document_id, tenant_uuid)
        emit_event(
            logging.ERROR,
            "document_processing_failed",
            tenant_id=tenant_id,
            error_type=type(error).__name__,
        )
        return

    started_at = perf_counter()
    for attempt in range(1, max_attempts + 1):
        try:
            chunk_count = index_document(path, tenant_id=tenant_id, document_id=document_id)
            elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
            threshold_ms = slow_document_processing_threshold_ms()
            if elapsed_ms >= threshold_ms:
                emit_event(
                    logging.WARNING,
                    "slow_document_processing",
                    tenant_id=tenant_id,
                    elapsed_ms=elapsed_ms,
                    threshold_ms=threshold_ms,
                    chunk_count=chunk_count,
                )
            return
        except Exception as error:
            emit_event(
                logging.ERROR,
                "document_processing_attempt_failed",
                tenant_id=tenant_id,
                error_type=type(error).__name__,
            )
            if attempt < max_attempts:
                sleep(min(0.1 * (2 ** (attempt - 1)), 1.0))

    _mark_job_failed(document_id, tenant_uuid)


def _mark_job_failed(document_id: UUID, tenant_uuid: UUID) -> None:
    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE documents SET status = 'failed', updated_at = now()
                WHERE id = %s AND tenant_id = %s AND status != 'deleted'
                """,
                (document_id, tenant_uuid),
            )
    except Exception:
        logging.getLogger("app.document_service").exception(
            "Failed to mark document processing as failed",
            extra={"document_id": str(document_id)},
        )
