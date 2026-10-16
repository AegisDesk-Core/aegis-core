import logging
import re
from time import perf_counter

from app.auth import database_tenant_id
from app.db.database import get_connection
from app.graph.state import SupportState
from app.observability import (
    emit_event,
    slow_vector_search_threshold_ms,
)
from app.services.document_service import get_embeddings


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


def retrieve(state: SupportState):
    tenant_id = state.get("tenant_id") or "unknown"
    query = state.get("rewritten_query") or state.get("query") or ""

    if not query.strip():
        state["retrieved_docs"] = []
        emit_event(
            logging.WARNING,
            "empty_retrieval",
            request_id=state.get("request_id"),
            tenant_id=tenant_id,
            user_id=state.get("user_id"),
            conversation_id=state.get("conversation_id"),
            retrieval_count=0,
        )
        return {"retrieved_docs": []}

    tenant_uuid = database_tenant_id(tenant_id)
    query_vector = get_embeddings().embed_query(query)
    search_terms = _search_terms(query)
    text_search_query = " | ".join(search_terms)

    with get_connection() as connection:
        row_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.tenant_id = %s AND d.status = 'ready'
            """,
            (tenant_uuid,),
        ).fetchone()[0]

        vector_search_started_at = perf_counter()
        vector_rows = connection.execute(
            """
            SELECT dc.content, dc.page_number, d.filename,
                     1 - (dc.embedding <=> %s::vector) AS similarity
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.tenant_id = %s AND d.status = 'ready'
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
                WHERE dc.tenant_id = %s AND d.status = 'ready'
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
    vector_search_ms = round((perf_counter() - vector_search_started_at) * 1000, 2)
    vector_search_threshold_ms = slow_vector_search_threshold_ms()
    if vector_search_ms >= vector_search_threshold_ms:
        emit_event(
            logging.WARNING,
            "slow_vector_search",
            request_id=state.get("request_id"),
            tenant_id=tenant_id,
            user_id=state.get("user_id"),
            conversation_id=state.get("conversation_id"),
            vector_search_ms=vector_search_ms,
            threshold_ms=vector_search_threshold_ms,
        )

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
    if not retrieved:
        emit_event(
            logging.WARNING,
            "empty_retrieval",
            request_id=state.get("request_id"),
            tenant_id=tenant_id,
            user_id=state.get("user_id"),
            conversation_id=state.get("conversation_id"),
            retrieval_count=0,
            vector_search_ms=vector_search_ms,
        )
    return {"retrieved_docs": retrieved}
