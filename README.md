# AI Customer Support Agent

A tenant-aware customer support assistant built with Python, FastAPI, LangGraph, RAG, and a Next.js frontend. The app answers support questions using indexed policy documents, validates the response against retrieved evidence, and escalates when the answer is unsupported or unsafe.

## Overview

This project combines:

- a Python backend API with validation and tenancy checks
- a LangGraph orchestration workflow for routing and grounding
- a FAISS-based retrieval layer over local knowledge documents
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
│   ├── __init__.py
│   ├── config.py
│   ├── final_response.py
│   ├── llm.py
│   └── main.py
├── data/
│   ├── documents/
│   └── vectorstore/
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

The FastAPI service exposes:

- `GET /health` for service health
- `GET /api/v1/chat/start` for tenant validation and welcome message
- `POST /api/v1/ask` for processing support questions

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

The retrieval layer in `app/rag/`:

- loads local knowledge content from `data/documents`
- builds or reuses a FAISS vector store under `data/vectorstore`
- retrieves the most relevant policy chunks for a query
- uses local fallback logic when a remote embedding provider is not available

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

## Notes

- The backend is a working prototype for grounded customer support.
- Retrieval is designed to be local-first, with FAISS-backed document search.
- The frontend is intentionally separate from the backend so the API and UI can be developed and deployed independently.
- The app is structured as a good starting point for a production-ready support assistant, with further work in monitoring, authentication, and stronger model evaluation.

---

## Future improvements

Possible next steps include:

- stronger multi-tenant isolation and configuration
- improved intent routing and answer validation
- more robust document ingestion and indexing
- persistent conversation memory and analytics
- deployment packaging with Docker and CI/CD
- richer observability and error tracing