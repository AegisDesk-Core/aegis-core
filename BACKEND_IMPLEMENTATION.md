# Backend Implementation Guide

This document describes the backend as it is implemented in this repository.
It follows a request from startup through authentication, persistence, graph
execution, document processing, and retrieval. It also records current
limitations so that prototype behavior is not mistaken for production
infrastructure.

## 1. Backend at a glance

The backend is a Python application built with FastAPI, LangGraph, PostgreSQL,
and pgvector.

- `main.py` at the repository root exports the FastAPI application as `app`.
- `app/main.py` configures the application, request telemetry, health check,
  chat routes, and the support-question workflow.
- `app/api.py` contains document, conversation, feedback, and admin routes.
- `app/auth.py` resolves tenant bearer tokens and admin credentials.
- `app/services/document_service.py` validates and stores uploads, processes
  PDFs, creates embeddings, persists chunks, and updates indexing job state.
- `app/services/conversation_service.py` persists conversations and messages
  and maintains bounded conversation memory.
- `app/rag/rag_main.py` searches tenant-scoped pgvector chunks.
- `app/graph/` and `app/agents/` implement the LangGraph support workflow.
- `app/guardrails/` validates inputs, evidence, and escalation behavior.
- `app/db/schema.py` defines the PostgreSQL schema and startup migrations.
- `app/db/database.py` owns the PostgreSQL connection pool.

PDF files are stored in tenant-specific local directories under
`data/documents/`. Document metadata, extracted chunks, and embedding vectors
are stored in PostgreSQL. The active retrieval path uses pgvector, not FAISS.

## 2. Environment and startup

Install the backend dependencies from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a root `.env` file. Do not commit it or put real credentials in
documentation. At minimum, the database settings need either a connection URL
or separate PostgreSQL credentials:

```env
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
```

Alternatively, configure `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`,
`POSTGRES_USER`, and `POSTGRES_PASSWORD`. The settings loader also supports
legacy lowercase names such as `host`, `port`, `dbname`, `user`, and `password`.

Other configuration used by the backend:

| Variable | Purpose |
| --- | --- |
| `API_ADMIN_TOKEN` | Separate bearer credential for `/api/v1/admin/metrics`. |
| `EMBEDDING_PROVIDER` | Set to `mistral` to try Mistral embeddings; otherwise local deterministic embeddings are used. |
| `MISTRAL_API_KEY` | Credential for the optional Mistral embedding provider. |
| `LLM_PROVIDER` | Selects the answer-generation provider configured in the LLM module. |
| `GEMINI_API_KEY` | Credential for the Google/Gemini LLM provider. |
| `OPENAI_API_KEY` | Credential for the OpenAI LLM provider. |
| `DB_MIN_SIZE`, `DB_MAX_SIZE`, `DB_TIMEOUT` | PostgreSQL connection-pool settings. |
| `SLOW_DOCUMENT_PROCESSING_MS`, `SLOW_VECTOR_SEARCH_MS` | Telemetry thresholds. |

Start the API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

At application startup, the FastAPI lifespan opens the connection pool, runs a
database connectivity check, and applies the schema SQL. The schema enables
`pgcrypto` and `vector`, creates or updates tables and indexes, and migrates
legacy document status `completed` to `ready`. The PostgreSQL role must be
permitted to create the required extension(s), tables, constraints, and indexes.
If startup fails, check the underlying database connection and schema error;
the startup exception wraps the original exception.

`GET /health` is a lightweight application health response. It does not perform
a fresh database check on every request.

## 3. Authentication and tenant identity

Tenant routes use the shared `authenticate_tenant` dependency from
`app/auth.py`. It reads the bearer credential and resolves the tenant from the
server-side `TENANT_BY_TOKEN` mapping. The client must not select a tenant by
sending a `tenant_id` in a body, query parameter, or header.

The current mapping is a development/demo arrangement: `demo-tenant` and
`customer-support` both map to `tenant-123`. It is not a tenant provisioning
or production credential-management system. Replace it with verified,
revocable credentials that resolve a principal and tenant from a trusted
identity provider or an appropriately secured API-key store before production
use.

The resolved tenant string is deterministically mapped to the UUID used in
database rows by `database_tenant_id`. The application uses the tenant from
authentication when writing or querying tenant-owned resources.

Admin metrics use a different dependency. The server must have `API_ADMIN_TOKEN`
configured; an absent or reused tenant token is rejected. Do not use a tenant
credential as the admin token. The current admin token is a single shared
credential, not role-based user administration.

## 4. HTTP API

All tenant-scoped routes require:

```http
Authorization: Bearer <tenant-token>
```

`POST /api/v1/documents` accepts a multipart `file` field. Other request
examples below use JSON.

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | Return `{"status":"ok"}`. |
| `GET` | `/api/v1/chat/start` | Tenant token | Return a welcome response. |
| `POST` | `/api/v1/ask` | Tenant token | Save a user message, run the support graph, persist the answer, and return it. |
| `POST` | `/api/v1/documents` | Tenant token | Validate/store a PDF, create a pending record, and queue indexing. |
| `GET` | `/api/v1/documents` | Tenant token | List this tenant's non-deleted documents; supports `limit` and `offset`. |
| `GET` | `/api/v1/documents/{document_id}` | Tenant token | Read one tenant-owned document's status and metadata. |
| `DELETE` | `/api/v1/documents/{document_id}` | Tenant token | Mark a tenant-owned document deleted and remove its local PDF. |
| `POST` | `/api/v1/documents/{document_id}/reindex` | Tenant token | Queue reindexing for a ready or failed document. |
| `GET` | `/api/v1/conversations` | Tenant token | List this tenant's non-deleted conversations; supports `limit` and `offset`. |
| `GET` | `/api/v1/conversations/{conversation_id}` | Tenant token | Read a tenant-owned conversation. |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | Tenant token | Read visible messages for a tenant-owned conversation. |
| `DELETE` | `/api/v1/conversations/{conversation_id}` | Tenant token | Delete a tenant-owned conversation and its dependent rows. |
| `POST` | `/api/v1/feedback` | Tenant token | Save a rating/comment for an assistant message in a tenant-owned conversation. |
| `GET` | `/api/v1/admin/metrics` | Admin token | Return global operational counts and in-process escalation metrics. |

### Uploading a document from a dashboard

Send `multipart/form-data` with a `file` field. The API responds with `202
Accepted`; its response is intentionally small and ready for a dashboard to use:

```json
{
  "document_id": "a4f4d992-9981-4aca-a1f9-092b6f46cde1",
  "filename": "returns-policy.pdf",
  "status": "pending"
}
```

Example using `curl`:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/documents" `
  -H "Authorization: Bearer <tenant-token>" `
  -F "file=@C:\path\to\returns-policy.pdf;type=application/pdf"
```

The `tenant_id` is not part of the upload contract. The server derives it from
the bearer token. The API enforces a 20 MiB upload limit, requires a `.pdf`
filename and a PDF file signature, strips client-supplied path components from
the filename, and stores the PDF beneath the authenticated tenant's local
directory.

Poll `GET /api/v1/documents/{document_id}` to display current job progress. A
document ID belonging to another tenant is not returned by these routes.

### Asking a support question

The ask endpoint expects a non-empty `message` and a `conversation_id`:

```json
{
  "message": "Can I return an item after 20 days?",
  "conversation_id": "customer-chat-001"
}
```

The service derives the internal conversation UUID in the context of the
authenticated tenant. The response contains the answer, intent, confidence,
citations/sources, escalation indicators, and a saved assistant `response_id`.

The `conversation_id` is a client-visible conversation key; it does not grant
access by itself. All conversation reads, writes, and deletes include the
authenticated tenant in their database predicates.

### Feedback payload

Feedback includes the conversation and assistant-message IDs, a rating from 1
through 5, and an optional comment of at most 2,000 characters:

```json
{
  "conversation_id": "00000000-0000-0000-0000-000000000001",
  "message_id": "00000000-0000-0000-0000-000000000002",
  "rating": 5,
  "comment": "This answered my question."
}
```

The insert succeeds only when the conversation and assistant message both
belong to the authenticated tenant.

## 5. Database and persistence

The schema is declared in `app/db/schema.py` and initialized through
`app/db/database.py`.

| Table | Role |
| --- | --- |
| `tenants` | Tenant records. |
| `users` | Users associated with tenants. The current API uses a deterministic service user per tenant. |
| `api_keys` | Schema support for tenant API-key records; current demo authentication does not look them up. |
| `conversations` | Tenant-owned conversation status and compact keyword memory. |
| `messages` | User/assistant/system messages with tenant and conversation IDs. |
| `message_citations` | Source document/page references for assistant messages. |
| `documents` | Tenant-owned document metadata, content hash, storage path, and processing status. |
| `document_chunks` | Tenant-owned text chunks and pgvector embeddings. |
| `feedback` | Tenant-owned conversation/message ratings and comments. |
| `audit_logs` | Schema for tenant-associated audit events; not a replacement for the current request telemetry. |

The `documents` table has a unique `(tenant_id, content_hash)` constraint.
`document_chunks` stores a `VECTOR(1536)` embedding and associates every row
with both `document_id` and `tenant_id`. Foreign keys cascade document chunks
when document metadata is physically removed, though the API's normal document
deletion is a soft delete.

Tenant isolation currently relies on server-derived tenant IDs and tenant
predicates in application queries. PostgreSQL row-level security policies are
not configured. The database therefore does not independently enforce tenant
isolation if future application code omits a predicate. Review any new SQL
against that rule and consider adding RLS as a second enforcement layer.

## 6. Document upload and indexing lifecycle

`app/services/document_service.py` owns document processing:

1. Validate the uploaded filename, PDF signature, and maximum size.
2. Compute a SHA-256 hash and check for an existing document for the same tenant.
3. Save new PDF bytes beneath `data/documents/<tenant-id>/`.
4. Insert a tenant-scoped `documents` row with `pending` status.
5. Schedule `process_document_job` using FastAPI `BackgroundTasks`.
6. Claim the job by changing `pending` to `processing` with both document ID and tenant ID in the update.
7. Extract text from PDF pages, retain source/page metadata, and split text into chunks (700 characters with 100 characters of overlap).
8. Create a 1,536-dimensional embedding for each chunk.
9. In a database transaction, verify the document is still tenant-owned and processing, replace its chunks, and mark the document `ready`.
10. Retry indexing failures up to three attempts with a short exponential delay; after the final failure, mark it `failed`.

The supported states are `pending`, `processing`, `ready`, `failed`, and
`deleted`. Reindexing is allowed for `ready` or `failed` documents and returns
them to `pending`. A second reindex request while a job is pending or processing
is rejected. A deleted document is excluded from retrieval and cannot be
reindexed.

The current job implementation uses FastAPI `BackgroundTasks`, which runs in
the API process. It is adequate for modest workloads but is not durable: a
process crash/restart can interrupt a job, and it does not provide a separate
worker pool, distributed scheduling, or a persistent retry queue. Use Celery,
RQ, Dramatiq, or a managed task queue with durable job records if those
properties are required.

The PDF bytes are currently stored on the API server's local filesystem. In a
multi-instance deployment, replace local storage with shared/object storage or
guarantee shared persistent storage available to all workers.

## 7. Embeddings and retrieval

The active vector store is PostgreSQL with pgvector. There is no active FAISS
index in the runtime retrieval path.

`get_embeddings()` in `document_service.py` selects the embedding provider:

- The default deterministic local hash embedder produces 1,536-dimensional vectors.
- When `EMBEDDING_PROVIDER=mistral`, the service attempts to create Mistral embeddings.
- If the optional Mistral integration cannot be initialized, the current implementation falls back to local embeddings.

The database vector column has a matching dimension of 1,536. If changing the
embedding model or its dimensions, plan a compatible database migration and
re-embed existing documents before mixing vectors from different models.

`retrieve()` in `app/rag/rag_main.py`:

1. Reads the tenant ID from `SupportState`, which is populated by the authenticated API request.
2. Converts it to the database tenant UUID.
3. Embeds the rewritten query.
4. Runs vector similarity search and PostgreSQL full-text search.
5. Joins chunks to document metadata and filters both searches by matching `tenant_id` and `documents.status = 'ready'`.
6. Combines candidates, calculates lexical/semantic relevance scores, and returns ranked document chunks to the graph.

This excludes `pending`, `processing`, `failed`, and `deleted` documents from
answer retrieval. The legacy fallback that scanned local PDFs and inferred a
tenant from filenames has been removed.

## 8. Conversation and support-answer flow

For `POST /api/v1/ask`, the request handler in `app/main.py`:

1. Authenticates the tenant and derives tenant/database user IDs.
2. Creates or verifies a conversation owned by that tenant.
3. Saves the customer's message.
4. Loads at most nine recent messages, each bounded to 1,200 characters, and the conversation's compact keyword memory.
5. Builds `SupportState` and invokes the LangGraph workflow.
6. Saves the assistant response and citations.
7. Returns the response and persisted assistant message ID.

`SupportState` is defined in `app/graph/state.py`. It currently includes query,
tenant and conversation IDs, request ID, optional user ID, bounded conversation
history, intent, rewritten query, retrieved/reranked documents, evidence,
confidence, answer, citations, sources, and escalation/grounding flags. A
persisted user `message_id` is not currently passed into graph state.

The graph in `app/graph/graph.py` composes nodes for request validation, intent
classification, routing, small-talk responses, query rewriting, retrieval,
reranking, evidence checks, response generation, grounding, escalation, and
response formatting. The exact node logic lives in `app/agents/`,
`app/guardrails/`, and `app/graph/`.

The transcript endpoint returns messages from the most recent 24 hours.
Persisted older messages are not all sent to the model; follow-up context is
bounded as described above.

## 9. Logging and monitoring

`app/main.py` installs HTTP middleware that generates a request ID, records
request completion, and adds the `X-Request-ID` response header. Uvicorn also
writes its own access log; seeing both a Uvicorn access line and a JSON
application event for the same request is expected.

`app/observability.py` emits newline-delimited JSON telemetry to stderr. The
formatter allowlists operational fields and omits message text, answers,
retrieved document contents, credentials, and other unapproved fields.
Events can include request/tenant/user/conversation IDs, route, status, timing,
retrieval count, evidence score, and escalation state.

Slow document processing and slow vector search emit warnings after their
configured thresholds. An in-process rolling escalation monitor emits an
alert when the sample and rate thresholds are met. These metrics are local to
one process; they are not durable or aggregated across multiple instances.
Uvicorn's `INFO: ... 200 OK` line and application JSON logs are informational,
not errors. HTTP 4xx/5xx results and failed processing events should be
investigated according to their status and event fields.

## 10. Tests and local checks

Run the backend test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The current tests cover graph behavior, API authentication, tenant upload
contract, document job state/retry behavior, schema status migration order, and
observability. Tests do not replace integration checks against the deployment's
actual PostgreSQL permissions, embeddings provider, storage, or external LLM.

Useful checks during development:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app tests
git --no-pager diff --check
```

## 11. Current limitations and production follow-up

- **Authentication:** tenant tokens are currently hardcoded demo mappings and both configured tokens resolve to one tenant. Use secure credential issuance, hashing, expiry/revocation, and a trusted tenant identity source.
- **Authorization:** admin metrics use one shared admin token rather than per-user roles and audit identities.
- **Database isolation:** application queries use tenant scoping, but PostgreSQL RLS is not enabled. Keep tenant predicates on every tenant-owned read/write and consider enforcing tenant context in the database.
- **Background work:** FastAPI `BackgroundTasks` is process-local and non-durable. Move indexing to a durable queue for large files, higher throughput, or reliable retry/recovery.
- **File storage:** documents are on local disk. Use object storage/shared storage for multi-instance deployments, with retention, encryption, and access controls.
- **Observability:** escalation metrics are in process memory. Export metrics/events to a centralized monitoring backend for multi-worker deployments.
- **Document handling:** only text-extractable PDFs are useful for the current pipeline; scanned/image-only PDFs may require OCR.
- **Embedding fallback:** the current provider selection can fall back to local embeddings. In production, make provider/model selection explicit and surface configuration errors rather than silently mixing models.
- **Feedback and audit:** feedback persistence exists; a full audit-log write pipeline and feedback analytics are separate work.
- **State correlation:** `request_id` is available in graph state, but the persisted incoming `message_id` and authenticated role are not currently graph state fields.
- **Tests:** add database-backed integration tests for cross-tenant read/write denial, transactional indexing, deletion races, concurrent duplicate uploads, and real task-queue recovery as the infrastructure evolves.

## 12. Source map

| Concern | Implementation |
| --- | --- |
| Application setup and ask flow | `app/main.py` |
| Document/conversation/feedback/admin routes | `app/api.py` |
| Tenant and admin authentication | `app/auth.py` |
| Upload, PDF parsing, embedding, pgvector writes, processing states | `app/services/document_service.py` |
| Conversation and message persistence | `app/services/conversation_service.py` |
| SQL schema and migrations | `app/db/schema.py` |
| Database pool | `app/db/database.py` |
| Tenant-filtered retrieval | `app/rag/rag_main.py` |
| Graph state and workflow | `app/graph/state.py`, `app/graph/graph.py` |
| Guardrails and intent agents | `app/guardrails/`, `app/agents/` |
| Telemetry and escalation monitoring | `app/observability.py` |