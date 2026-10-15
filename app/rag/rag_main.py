import hashlib
import math
import re
from os import environ
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import get_env
from app.db.database import get_connection
from app.graph.state import SupportState

try:
    from langchain_mistralai import MistralAIEmbeddings
except Exception:
    MistralAIEmbeddings = None


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


def _get_embeddings():
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


DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "data" / "documents"
CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
RETRIEVAL_CANDIDATES = 20
STOP_WORDS = {
    "a", "about", "after", "and", "are", "can", "for", "from", "how", "i",
    "in", "is", "it", "me", "my", "of", "on", "or", "the", "this", "to",
    "what", "when", "where", "which", "who", "with", "you", "your",
}
QUERY_SYNONYMS = {
    "return": {"returned", "returning", "returns"},
    "returned": {"return", "returning", "returns"},
    "returning": {"return", "returned", "returns"},
    "returns": {"return", "returned", "returning"},
    "product": {"products"},
    "products": {"product"},
    "contact": {"support", "phone", "telephone"},
    "number": {"phone", "telephone"},
    "phone": {"number", "telephone"},
    "telephone": {"number", "phone"},
    "email": {"mail"},
    "mail": {"email"},
    "step": {"stage", "stages", "lifecycle", "process"},
    "steps": {"stage", "stages", "lifecycle", "process"},
    "stage": {"step", "steps", "lifecycle", "process"},
    "stages": {"step", "steps", "lifecycle", "process"},
    "confirmation": {"confirm", "confirmed", "processing", "checkout"},
    "confirm": {"confirmation", "confirmed"},
    "confirmed": {"confirmation", "confirm"},
}


def _pdf_tenant_id(pdf_path: Path) -> str:
    prefix = pdf_path.stem.split("__", 1)[0]
    return prefix if prefix.startswith("tenant-") else "tenant-123"


def _tenant_uuid(tenant_id: str) -> UUID:
    try:
        return UUID(tenant_id)
    except ValueError:
        return uuid5(NAMESPACE_URL, f"customer-support-tenant:{tenant_id}")


def _file_fingerprint(pdf_path: Path) -> str:
    digest = hashlib.sha256()
    with pdf_path.open("rb") as document:
        for block in iter(lambda: document.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _search_terms(query: str) -> list[str]:
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    terms.difference_update(STOP_WORDS)
    expanded_terms = set(terms)
    for term in terms:
        expanded_terms.update(QUERY_SYNONYMS.get(term, ()))
    return sorted(expanded_terms)


def _lexical_coverage(query: str, content: str) -> float:
    terms = set(re.findall(r"[a-z0-9]+", query.lower())) - STOP_WORDS
    if not terms:
        return 0.0

    content_terms = set(re.findall(r"[a-z0-9]+", content.lower()))
    matched = 0
    for term in terms:
        alternatives = QUERY_SYNONYMS.get(term, set()) | {term}
        if alternatives.intersection(content_terms):
            matched += 1
    return matched / len(terms)


def _retrieval_score(query: str, content: str, similarity: float) -> float:
    semantic_score = max(0.0, min(float(similarity or 0.0), 1.0))
    lexical_score = _lexical_coverage(query, content)
    return round(0.7 * lexical_score + 0.3 * semantic_score, 4)


def _load_pdf_documents(pdf_path: Path, tenant_id: str) -> list[Document]:
    reader = PdfReader(str(pdf_path))
    return [
        Document(
            page_content=page.extract_text() or "",
            metadata={
                "source": pdf_path.name,
                "page": page_number,
                "tenant_id": tenant_id,
            },
        )
        for page_number, page in enumerate(reader.pages, start=1)
        if page.extract_text()
    ]


def _index_pdf_documents(pdf_path: Path) -> None:
    tenant_id = _pdf_tenant_id(pdf_path)
    embeddings = _get_embeddings()
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    documents = _load_pdf_documents(pdf_path, tenant_id)
    chunks = splitter.split_documents(documents)
    if not chunks:
        return

    with get_connection() as connection:
        tenant_uuid = _tenant_uuid(tenant_id)
        connection.execute(
            """
            INSERT INTO tenants (id, name)
            VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET updated_at = now()
            """,
            (tenant_uuid, tenant_id),
        )

        document_hash = _file_fingerprint(pdf_path)
        document_row = connection.execute(
            """
            SELECT id
            FROM documents
            WHERE tenant_id = %s AND content_hash = %s
            """,
            (tenant_uuid, document_hash),
        ).fetchone()

        if document_row is None:
            document_row = connection.execute(
                """
                INSERT INTO documents
                    (tenant_id, filename, storage_path, content_hash, status, embedding_model, chunk_size, chunk_overlap)
                VALUES (%s, %s, %s, %s, 'completed', 'local-hash-384', %s, %s)
                RETURNING id
                """,
                (tenant_uuid, pdf_path.name, str(pdf_path), document_hash, CHUNK_SIZE, CHUNK_OVERLAP),
            ).fetchone()
        else:
            connection.execute(
                "UPDATE documents SET updated_at = now(), status = 'completed' WHERE id = %s",
                (document_row[0],),
            )

        if document_row is None:
            return

        document_id = document_row[0]
        for chunk_number, chunk in enumerate(chunks, start=1):
            chunk_vector = embeddings.embed_query(chunk.page_content)
            connection.execute(
                """
                INSERT INTO document_chunks
                    (document_id, tenant_id, chunk_number, content, page_number, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, chunk_number) DO UPDATE
                    SET content = EXCLUDED.content,
                        page_number = EXCLUDED.page_number,
                        embedding = EXCLUDED.embedding,
                        created_at = now()
                """,
                (
                    document_id,
                    tenant_uuid,
                    chunk_number,
                    chunk.page_content,
                    int(chunk.metadata.get("page", 1)),
                    chunk_vector,
                ),
            )


def _index_all_documents() -> None:
    for pdf_path in sorted(DOCUMENTS_DIR.glob("*.pdf")):
        _index_pdf_documents(pdf_path)


def retrieve(state: SupportState):
    tenant_id = state.get("tenant_id") or "unknown"
    query = state.get("rewritten_query") or state.get("query") or ""

    if not query.strip():
        state["retrieved_docs"] = []
        return {"retrieved_docs": []}

    tenant_uuid = _tenant_uuid(tenant_id)
    query_vector = _get_embeddings().embed_query(query)
    search_terms = _search_terms(query)
    text_search_query = " | ".join(search_terms)

    with get_connection() as connection:
        row_count = connection.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE tenant_id = %s",
            (tenant_uuid,),
        ).fetchone()[0]

        if row_count == 0:
            _index_all_documents()

        vector_rows = connection.execute(
            """
            SELECT dc.content, dc.page_number, d.filename,
                     1 - (dc.embedding <=> %s::vector) AS similarity
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.tenant_id = %s
            ORDER BY dc.embedding <=> %s::vector
            LIMIT %s
            """,
            (query_vector, tenant_uuid, query_vector, RETRIEVAL_CANDIDATES),
        ).fetchall()

        lexical_rows = []
        if text_search_query:
            lexical_rows = connection.execute(
                """
                SELECT dc.content, dc.page_number, d.filename,
                       1 - (dc.embedding <=> %s::vector) AS similarity,
                       ts_rank_cd(
                           to_tsvector('english', dc.content),
                           to_tsquery('english', %s)
                       ) AS lexical_score
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE dc.tenant_id = %s
                  AND to_tsvector('english', dc.content)
                      @@ to_tsquery('english', %s)
                ORDER BY lexical_score DESC, dc.embedding <=> %s::vector
                LIMIT %s
                """,
                (
                    query_vector,
                    text_search_query,
                    tenant_uuid,
                    text_search_query,
                    query_vector,
                    RETRIEVAL_CANDIDATES,
                ),
            ).fetchall()

    candidates = {}
    for row in vector_rows:
        content, page_number, filename, similarity = row
        key = (filename, page_number, content)
        candidates[key] = {
            "content": content,
            "page": page_number,
            "filename": filename,
            "similarity": similarity,
        }

    for row in lexical_rows:
        content, page_number, filename, similarity, _lexical_score = row
        key = (filename, page_number, content)
        candidate = candidates.setdefault(
            key,
            {
                "content": content,
                "page": page_number,
                "filename": filename,
                "similarity": similarity,
            },
        )
        if candidate["similarity"] is None and similarity is not None:
            candidate["similarity"] = similarity

    retrieved = []
    for candidate in candidates.values():
        content = candidate["content"]
        similarity = candidate["similarity"]
        score = _retrieval_score(query, content, similarity)
        retrieved.append(
            {
                "content": content,
                "metadata": {
                    "source": candidate["filename"],
                    "page": int(candidate["page"] or 1),
                    "tenant_id": tenant_id,
                },
                "score": score,
            }
        )

    retrieved.sort(key=lambda item: item["score"], reverse=True)
    retrieved = retrieved[:5]
    state["retrieved_docs"] = retrieved
    return {"retrieved_docs": retrieved}
