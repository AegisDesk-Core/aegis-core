# AI Customer Support Agent

A tenant-aware customer support assistant built with Python, FastAPI, LangGraph, RAG, and a Next.js frontend. The app answers support questions using indexed policy documents, validates the response against retrieved evidence, and escalates when the answer is unsupported or unsafe.

## Overview

This project combines:

- a Python backend API with validation and tenancy checks
- a LangGraph orchestration workflow for routing and grounding
- a PostgreSQL/pgvector retrieval layer over tenant-scoped knowledge documents
- a guardrail pipeline for hallucination prevention and escalation
- a Next.js frontend for interactive support chat

It is designed to help support teams answer questions such as:

- refund and return eligibility
- shipping delays or delivery status
- product compatibility or policy questions
- general company policy lookup from a tenant-scoped knowledge base

---

## Current app structure

```text
AI CUSTOMER SUPPOERT/
├── app/
│   ├── agents/
│   ├── db/
│   ├── graph/
│   ├── guardrails/
│   ├── prompts/
│   ├── rag/
│   ├── services/
│   │   └── document_service.py
│   ├── __init__.py
│   ├── config.py
│   ├── final_response.py
│   ├── llm.py
│   └── main.py
├── data/
│   ├── documents/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── README.md
│   └── next.config.ts
├── tests/
│   ├── test_graph.py
│   └── test_rag_cli.py
├── main.py
├── requirements.txt
├── .env
├── README.md
└── .gitignore
```

---

## What the app does

### Backend

The FastAPI service exposes `GET /health` and these versioned endpoints:

| Method | Endpoint | Access |
| --- | --- | --- |
| `GET` | `/api/v1/chat/start` | Tenant bearer token |
| `POST` | `/api/v1/ask` | Tenant bearer token |
| `POST` | `/api/v1/documents` | Tenant bearer token; PDF upload (20 MB maximum) |
| `GET` | `/api/v1/documents` | Tenant bearer token |
| `GET` | `/api/v1/documents/{document_id}` | Tenant bearer token |
| `DELETE` | `/api/v1/documents/{document_id}` | Tenant bearer token |
| `POST` | `/api/v1/documents/{document_id}/reindex` | Tenant bearer token |
| `GET` | `/api/v1/conversations` | Tenant bearer token |
| `GET` | `/api/v1/conversations/{conversation_id}` | Tenant bearer token |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | Tenant bearer token |
| `DELETE` | `/api/v1/conversations/{conversation_id}` | Tenant bearer token |
| `POST` | `/api/v1/feedback` | Tenant bearer token |
| `GET` | `/api/v1/admin/metrics` | Admin bearer token (`API_ADMIN_TOKEN`) |

Tenant-scoped document and conversation queries are restricted to the
authenticated tenant. Document uploads are indexed asynchronously and return
`202 Accepted` with status `pending`; jobs transition through `processing` to
`ready`, or to `failed` if indexing fails; deleting a document marks it `deleted`.
Reindexing returns `202 Accepted` with status `pending`. Poll the document detail
endpoint to check job progress.
An already queued or running document cannot be queued for reindexing again.

Dashboard clients can upload a PDF with a multipart `file` field and tenant
bearer token:

```http
POST /api/v1/documents
Authorization: Bearer <tenant-token>
Content-Type: multipart/form-data
```

The response includes the document ID, original filename, and current processing
status:

```json
{
  "document_id": "a4f4d992-9981-4aca-a1f9-092b6f46cde1",
  "filename": "returns-policy.pdf",
  "status": "pending"
}
```

Tenant identity is resolved from the bearer token; a client-supplied
`tenant_id` is not used.
Admin metrics are not accessible with tenant tokens; configure a separate,
high-entropy `API_ADMIN_TOKEN` in the backend environment.

The request flow includes:

1. bearer-token authentication for tenant session validation
2. loading or creating a tenant-owned conversation and saving the customer message
3. passing the persistent keyword memory and at most 9 recent persisted messages to query rewriting and answer generation
4. intent classification and route selection
5. retrieval and reranking over the tenant knowledge base
6. evidence scoring and grounding checks
7. answer generation with source citations
8. saving the assistant response and returning its message ID
9. escalation when the answer is not grounded or needs a human

Conversation messages remain stored for follow-up context, while the transcript API
returns only messages from the last 24 hours. The chat UI reloads that visible
transcript when the customer returns to the same conversation. Older messages are
not sent as an unlimited prompt history; the model receives the compact keyword
memory plus at most 9 recent persisted messages, each limited to 1,200 characters.

### LangGraph workflow

The workflow is built in `app/graph/graph.py` and uses the shared state in `app/graph/state.py`.

The main stages include:

- validation
- intent detection
- direct welcome responses for greetings and customer introductions
- routing
- query rewriting
- retrieval
- reranking
- evidence and context verification, with unrelated requests flagged for human support
- final answer assembly
- escalation logic

### RAG and retrieval

Document uploads and indexing are managed by `app/services/document_service.py`.
It validates and stores tenant uploads, extracts and chunks PDF text, creates
embeddings, persists chunks and vectors to PostgreSQL/pgvector, and manages job
status and retries. Retrieval in `app/rag/rag_main.py` filters by authenticated
tenant and only searches documents with `ready` status. A deterministic local
embedding provider is used when the configured remote provider is unavailable.

### Guardrails

Safety checks are implemented under `app/guardrails/` for:

- invalid or empty user requests
- prompt injection or unsafe input
- unsupported or low-confidence answers
- missing evidence
- escalation to a human support flow

### Frontend

The frontend app in `frontend/` is a Next.js chat interface that:

- connects to the backend API
- validates the bearer token
- sends chat history and messages
- displays answer text and citations
- allows configuration of backend URL and tenant token

---

## Environment setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Create or update a `.env` file in the project root. The project currently reads environment values via `app/config.py` and `app/db/settings.py`.

Typical environment variables:

```env
LLM_PROVIDER=google
LLM_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=your_api_key_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/customer_support
```

You can also use the OpenAI provider with:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
```

> The backend expects a valid tenant token, and the default demo token configured is `demo-tenant`.
Set `API_ADMIN_TOKEN` to enable the admin metrics endpoint.

---

## Run the backend

From the project root:

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

This serves the API at:

- `http://localhost:8000/health`
- `http://localhost:8000/api/v1/ask`

---

## Run the frontend

Open a new terminal, then start the UI:

```bash
cd frontend
npm install
npm run dev
```

The frontend will run at:

- `http://localhost:3000`

In the UI, set the backend URL to:

```text
http://localhost:8000
```

and use the token:

```text
demo-tenant
```

---

## API example

Example request:

```http
POST /api/v1/ask
Authorization: Bearer demo-tenant
Content-Type: application/json
```

```json
{
  "message": "Can I return my laptop after 20 days?",
  "conversation_id": "conv_123",
  "history": [
    {"role": "assistant", "content": "What is your question or problem today? I am here to help."}
  ]
}
```

Example response shape:

```json
{
  "answer": "You are eligible for a return within 30 days...",
  "intent": "refund",
  "confidence": 0.91,
  "citations": [
    {"filename": "returns_policy.pdf", "page": 3, "excerpt": "Returns are accepted within 30 days..."}
  ],
  "sources": ["returns_policy.pdf"],
  "needs_human": false,
  "escalated": false
}
```

---

## Testing

Run the Python test suite from the repository root:

```bash
pytest
```

This project includes graph and RAG-related checks under `tests/`.

---

## Monitoring and logging

The backend writes newline-delimited JSON telemetry to stderr. Each HTTP request
receives a generated `X-Request-ID` response header and a completion event with
the request ID, tenant/user/conversation IDs when available, intent, retrieval
count, evidence score, answer and LLM latency, escalation status, HTTP status,
and error type. Authentication failures (401) and server errors (500) are
logged as warnings.

Operational events are also emitted for empty retrievals, low evidence scores,
slow vector searches, slow document processing, and high escalation rates. A
high-escalation alert uses the latest 1,000 successfully processed chat turns,
requires at least 10 samples and a rate of 50% or more, and is rate-limited to
one alert every five minutes. Document processing is considered slow at 5
seconds; vector searches are considered slow at 500 ms. Override these
thresholds with `SLOW_DOCUMENT_PROCESSING_MS` and `SLOW_VECTOR_SEARCH_MS`.

Logs are deliberately limited to operational metadata and do not include chat
messages, answer text, retrieved document content, credentials, or exception
messages. The escalation-rate window is in process memory; deployments that
need durable or cross-instance aggregation should forward these JSON events to
their monitoring platform.

---

## Notes

- The backend is a working prototype for grounded customer support.
- PDF files are stored locally, while document chunks and vectors are stored in PostgreSQL/pgvector.
- The frontend is intentionally separate from the backend so the API and UI can be developed and deployed independently.
- The app is structured as a good starting point for a production-ready support assistant, with further work in authentication and stronger model evaluation.

---

## Future improvements

Possible next steps include:

- stronger multi-tenant isolation and configuration
- improved intent routing and answer validation
- more robust document ingestion and indexing
- persistent conversation memory and analytics
- deployment packaging with Docker and CI/CD