from typing import Any
from uuid import UUID

from app.db.database import get_connection


def save_chat_turn(
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    user_message: str,
    assistant_message: str,
    intent: str,
    confidence: float,
    needs_human: bool,
    citations: list[dict[str, Any]] | None = None,
) -> None:
    """Persist one user/assistant turn and its citations atomically."""
    status = "active"
    citations = citations or []

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
        connection.execute(
            """
            INSERT INTO conversations (id, tenant_id, user_id, status)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                updated_at = now()
            """,
            (conversation_id, tenant_id, user_id, status),
        )
        connection.execute(
            """
            INSERT INTO messages (conversation_id, tenant_id, role, content)
            VALUES (%s, %s, 'user', %s)
            """,
            (conversation_id, tenant_id, user_message),
        )
        assistant_row = connection.execute(
            """
            INSERT INTO messages
                (conversation_id, tenant_id, role, content, intent, confidence)
            VALUES (%s, %s, 'assistant', %s, %s, %s)
            RETURNING id
            """,
            (conversation_id, tenant_id, assistant_message, intent, confidence),
        ).fetchone()

        assistant_message_id = assistant_row[0]
        for citation in citations:
            document = str(citation.get("document", ""))
            page = int(citation.get("page", 1))
            connection.execute(
                """
                INSERT INTO message_citations (message_id, document, page)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (assistant_message_id, document, page),
            )

        connection.execute(
            """
            UPDATE conversations
            SET updated_at = now()
            WHERE id = %s AND tenant_id = %s
            """,
            (conversation_id, tenant_id),
        )


def delete_conversation(*, conversation_id: UUID, tenant_id: UUID) -> bool:
    """Delete a conversation and all of its associated rows for the tenant."""
    with get_connection() as connection:
        result = connection.execute(
            """
            DELETE FROM conversations
            WHERE id = %s AND tenant_id = %s
            RETURNING id
            """,
            (conversation_id, tenant_id),
        )
        deleted = result.fetchone() is not None
        return deleted
