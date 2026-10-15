import re
from typing import Any, Literal
from uuid import UUID

from psycopg import Connection

from app.db.database import get_connection


MAX_RECENT_MESSAGES = 9
MAX_RECENT_MESSAGE_CHARS = 1200
MAX_MEMORY_KEYWORDS = 100
MEMORY_TOKEN_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.\w+|[\w][\w-]*", re.IGNORECASE)
MEMORY_STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been", "before",
    "being", "between", "but", "can", "could", "did", "does", "doing", "during",
    "each", "for", "from", "get", "got", "had", "has", "have", "here", "how",
    "into", "its", "just", "like", "make", "many", "more", "most", "much", "need",
    "not", "only", "other", "our", "out", "over", "please", "same", "should",
    "some", "such", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "through", "under", "use", "very", "was",
    "were", "what", "when", "where", "which", "while", "who", "why", "will",
    "with", "would", "you", "your",
}


def _updated_memory_keywords(existing: str, content: str) -> str:
    keywords = [keyword for keyword in existing.split() if keyword]
    for match in MEMORY_TOKEN_PATTERN.finditer(content[:5000]):
        keyword = match.group().lower()[:80]
        if keyword in MEMORY_STOP_WORDS or (len(keyword) < 2 and not keyword.isdigit()):
            continue
        if keyword in keywords:
            keywords.remove(keyword)
        keywords.append(keyword)
    keywords = keywords[-MAX_MEMORY_KEYWORDS:]
    while keywords and len(" ".join(keywords)) > 1200:
        keywords.pop(0)
    return " ".join(keywords)


def _update_memory_keywords(
    connection: Connection,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    content: str,
) -> None:
    row = connection.execute(
        """
        SELECT memory_keywords
        FROM conversations
        WHERE id = %s AND tenant_id = %s
        FOR UPDATE
        """,
        (conversation_id, tenant_id),
    ).fetchone()
    if row is None:
        raise LookupError("Conversation not found.")
    connection.execute(
        """
        UPDATE conversations SET memory_keywords = %s
        WHERE id = %s AND tenant_id = %s
        """,
        (
            _updated_memory_keywords(row[0], content),
            conversation_id,
            tenant_id,
        ),
    )


def create_conversation(
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> UUID:
    """Create a conversation, or leave an existing tenant-owned one unchanged."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tenants (id, name)
            VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET updated_at = now()
            """,
            (tenant_id, str(tenant_id)),
        )
        connection.execute(
            """
            INSERT INTO users (id, tenant_id, email, external_auth_id, role)
            VALUES (%s, %s, %s, %s, 'user')
            ON CONFLICT (id) DO NOTHING
            """,
            (user_id, tenant_id, f"service+{tenant_id}@internal.local", f"service:{tenant_id}"),
        )
        result = connection.execute(
            """
            INSERT INTO conversations (id, tenant_id, user_id, status)
            VALUES (%s, %s, %s, 'active')
            ON CONFLICT (id) DO UPDATE SET updated_at = now()
            WHERE conversations.tenant_id = EXCLUDED.tenant_id
                AND conversations.user_id = EXCLUDED.user_id
                AND conversations.status != 'deleted'
            RETURNING id
            """,
            (conversation_id, tenant_id, user_id),
        )
        row = result.fetchone()
        if row is None:
            raise ValueError("Conversation ID is already used by another customer.")
        return row[0]


def get_conversation(*, conversation_id: UUID, tenant_id: UUID) -> dict[str, Any] | None:
    """Load a conversation only when it belongs to the requesting tenant."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, tenant_id, user_id, status, memory_keywords
            FROM conversations
            WHERE id = %s AND tenant_id = %s AND status != 'deleted'
            """,
            (conversation_id, tenant_id),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "tenant_id": row[1],
        "user_id": row[2],
        "status": row[3],
        "memory_keywords": row[4],
    }


def save_message(
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    content: str,
    role: Literal["user", "assistant"] = "user",
) -> UUID:
    """Persist one message in an existing tenant-owned conversation."""
    with get_connection() as connection:
        result = connection.execute(
            """
            INSERT INTO messages (conversation_id, tenant_id, role, content)
            SELECT id, tenant_id, %s, %s
            FROM conversations
            WHERE id = %s AND tenant_id = %s AND status != 'deleted'
            RETURNING id
            """,
            (role, content, conversation_id, tenant_id),
        )
        row = result.fetchone()
        if row is None:
            raise LookupError("Conversation not found.")
        _update_memory_keywords(
            connection,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            content=content,
        )
        connection.execute(
            """
            UPDATE conversations SET updated_at = now()
            WHERE id = %s AND tenant_id = %s
            """,
            (conversation_id, tenant_id),
        )
        return row[0]


def get_recent_messages(
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    exclude_message_id: UUID | None = None,
    limit: int = MAX_RECENT_MESSAGES,
) -> list[dict[str, Any]]:
    """Return a bounded, chronological context window from the full conversation."""
    message_limit = min(max(limit, 0), MAX_RECENT_MESSAGES)
    if message_limit == 0:
        return []

    with get_connection() as connection:
        exclusion_sql = ""
        parameters: tuple[Any, ...] = (
            MAX_RECENT_MESSAGE_CHARS,
            conversation_id,
            tenant_id,
        )
        if exclude_message_id is not None:
            exclusion_sql = "AND id != %s"
            parameters += (exclude_message_id,)
        rows = connection.execute(
            f"""
            SELECT id, role, LEFT(content, %s), created_at
            FROM messages
            WHERE conversation_id = %s
                AND tenant_id = %s
                {exclusion_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            parameters + (message_limit,),
        ).fetchall()

    return [
        {"id": row[0], "role": row[1], "content": row[2], "created_at": row[3]}
        for row in reversed(rows)
    ]


def get_visible_messages(
    *,
    conversation_id: UUID,
    tenant_id: UUID,
) -> list[dict[str, Any]]:
    """Return messages from the last 24 hours for the chat transcript."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT m.id, m.role, m.content, m.created_at,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'document', mc.document,
                            'page', mc.page
                        )
                    ) FILTER (WHERE mc.message_id IS NOT NULL),
                    '[]'::json
                )
            FROM messages AS m
            LEFT JOIN message_citations AS mc ON mc.message_id = m.id
            WHERE m.conversation_id = %s
                AND m.tenant_id = %s
                AND m.created_at >= now() - interval '24 hours'
            GROUP BY m.id
            ORDER BY m.created_at, m.id
            """,
            (conversation_id, tenant_id),
        ).fetchall()
    return [
        {
            "id": row[0],
            "role": row[1],
            "content": row[2],
            "created_at": row[3],
            "citations": row[4],
        }
        for row in rows
    ]


def save_assistant_response(
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    content: str,
    intent: str,
    confidence: float,
    citations: list[dict[str, Any]] | None = None,
) -> UUID:
    """Persist an assistant response and its citations; return its message ID."""
    citations = citations or []
    with get_connection() as connection:
        result = connection.execute(
            """
            INSERT INTO messages
                (conversation_id, tenant_id, role, content, intent, confidence)
            SELECT id, tenant_id, 'assistant', %s, %s, %s
            FROM conversations
            WHERE id = %s AND tenant_id = %s AND status != 'deleted'
            RETURNING id
            """,
            (content, intent, confidence, conversation_id, tenant_id),
        )
        row = result.fetchone()
        if row is None:
            raise LookupError("Conversation not found.")
        message_id = row[0]
        _update_memory_keywords(
            connection,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            content=content,
        )

        for citation in citations:
            connection.execute(
                """
                INSERT INTO message_citations (message_id, document, page)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    message_id,
                    str(citation.get("document", "")),
                    int(citation.get("page", 1)),
                ),
            )
        connection.execute(
            """
            UPDATE conversations SET updated_at = now()
            WHERE id = %s AND tenant_id = %s
            """,
            (conversation_id, tenant_id),
        )
        return message_id
