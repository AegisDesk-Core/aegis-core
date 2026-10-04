SCHEMA_TEMPLATE = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tenants_status_check
        CHECK (status IN ('active', 'inactive', 'suspended'))
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash TEXT,
    external_auth_id VARCHAR(255),
    role VARCHAR(30) NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT users_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,
    CONSTRAINT users_role_check
        CHECK (role IN ('admin', 'user'))
);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    key_hash VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT api_keys_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,
    CONSTRAINT api_keys_key_hash_unique
        UNIQUE (key_hash)
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT conversations_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,
    CONSTRAINT conversations_user_fk
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT conversations_status_check
        CHECK (status IN ('active', 'archived', 'deleted'))
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    intent VARCHAR(100),
    confidence REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT messages_conversation_fk
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,
    CONSTRAINT messages_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,
    CONSTRAINT messages_role_check
        CHECK (role IN ('user', 'assistant', 'system')),
    CONSTRAINT messages_confidence_check
        CHECK (
            confidence IS NULL
            OR confidence >= 0
            AND confidence <= 1
        )
);

CREATE TABLE IF NOT EXISTS message_citations (
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    document TEXT NOT NULL,
    page INTEGER NOT NULL,
    PRIMARY KEY (message_id, document, page)
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    filename VARCHAR(500) NOT NULL,
    storage_path TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'processing',
    embedding_model VARCHAR(255),
    chunk_size INTEGER,
    chunk_overlap INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT documents_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,
    CONSTRAINT documents_status_check
        CHECK (
            status IN (
                'processing',
                'ready',
                'completed',
                'failed',
                'deleted'
            )
        ),
    CONSTRAINT documents_chunk_size_check
        CHECK (chunk_size IS NULL OR chunk_size > 0),
    CONSTRAINT documents_chunk_overlap_check
        CHECK (chunk_overlap IS NULL OR chunk_overlap >= 0),
    CONSTRAINT documents_tenant_hash_unique
        UNIQUE (tenant_id, content_hash)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    chunk_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_chunks_document_fk
        FOREIGN KEY (document_id)
        REFERENCES documents(id)
        ON DELETE CASCADE,
    CONSTRAINT document_chunks_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,
    CONSTRAINT document_chunks_number_check
        CHECK (chunk_number >= 0),
    CONSTRAINT document_chunks_page_check
        CHECK (page_number IS NULL OR page_number > 0),
    CONSTRAINT document_chunks_unique
        UNIQUE (document_id, chunk_number)
);

CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    conversation_id UUID NOT NULL,
    message_id UUID NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT feedback_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,
    CONSTRAINT feedback_conversation_fk
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,
    CONSTRAINT feedback_message_fk
        FOREIGN KEY (message_id)
        REFERENCES messages(id)
        ON DELETE CASCADE,
    CONSTRAINT feedback_rating_check
        CHECK (rating >= 1 AND rating <= 5)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    iid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT audit_logs_tenant_fk
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,
    CONSTRAINT audit_logs_user_fk
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS users_tenant_id_idx ON users (tenant_id);
CREATE INDEX IF NOT EXISTS api_keys_tenant_id_idx ON api_keys (tenant_id);
CREATE INDEX IF NOT EXISTS conversations_tenant_updated_idx ON conversations (tenant_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS messages_conversation_created_idx ON messages (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS messages_tenant_created_idx ON messages (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS message_citations_document_idx ON message_citations (document, page);
CREATE INDEX IF NOT EXISTS documents_tenant_status_idx ON documents (tenant_id, status);
CREATE INDEX IF NOT EXISTS chunks_tenant_id_idx ON document_chunks (tenant_id);
CREATE INDEX IF NOT EXISTS feedback_conversation_idx ON feedback (conversation_id);
CREATE INDEX IF NOT EXISTS audit_logs_tenant_created_idx ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
ON document_chunks USING hnsw (embedding vector_cosine_ops);
"""


def build_schema_sql() -> str:
    return SCHEMA_TEMPLATE
