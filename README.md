# AI Customer Support Agent

This project is a customer support assistant built with Python, FastAPI, LangGraph, and retrieval-augmented generation (RAG). It is designed to answer customer support questions using company policy documents, validate the answer against evidence, and escalate when the information is missing or unsafe.

## Project goal

The system helps support teams answer questions like:

- refund and return eligibility
- shipping or delivery status
- product specifications and compatibility
- general policy-based questions from a tenant-specific knowledge base

The workflow is built to avoid hallucinations by checking the retrieved documents before returning an answer.

---

## What has already been done

### 1. FastAPI service

A REST API has been implemented with:

- health endpoint: `/health`
- support endpoint: `/api/v1/ask`
- bearer-token authentication for tenant validation
- request validation for required message and conversation metadata

### 2. LangGraph workflow

The core logic is organized as a LangGraph state workflow with these stages:

- request validation
- intent classification
- intent routing
- query rewriting
- document retrieval
- reranking
- evidence verification
- answer generation
- grounding check
- escalation
- final response formatting

This workflow is defined in `app/graph/graph.py` and uses the state schema in `app/graph/state.py`.

### 3. Tenant-aware retrieval system

The RAG layer:

- reads PDF documents from the `data/documents` folder
- splits them into chunks
- creates or reuses a FAISS vector store for each tenant
- retrieves the most relevant policy chunks based on the rewritten user query
- uses a local hashing-based embedding fallback so the project can run without a remote model dependency

This is implemented in `app/rag/rag_main.py`.

### 4. Guardrails and safety checks

The project includes guardrail logic for:

- empty or invalid queries
- prompt injection attempts
- unsafe or unsupported requests
- absence of relevant evidence
- ungrounded answers that are not supported by the retrieved documents
- escalation to a human support flow when confidence is low

These checks are in the `app/guardrails` package.

### 5. Intent-based handling

The agent already supports a basic routing structure for:

- `refund`
- `shipping`
- `product`
- `other`

The `app/agents/router.py` module classifies user questions and routes them into the proper support workflow.

### 6. Response generation and formatting

The final answer flow:

- assembles evidence-backed answers
- stores source references
- returns a structured JSON payload with answer, intent, confidence, sources, and escalation status

### 7. Basic test coverage

The project includes a simple test suite in `tests/test_graph.py` to validate:

- the state structure is complete
- the expected workflow nodes exist

---

## Project structure

```text
AI CUSTOMER SUPPOERT/
├── app/
│   ├── agents/
│   ├── config.py
│   ├── final_response.py
│   ├── graph/
│   ├── guardrails/
│   ├── llm.py
│   ├── main.py
│   ├── prompts/
│   └── rag/
├── data/
│   ├── documents/
│   └── vectorstore/
├── tests/
├── main.py
├── README.md
├── requirements.txt
└── .env.example (if added later)
```

---

## How the system works

1. A user sends a query through the API.
2. The request is validated and checked for prompt injection or invalid content.
3. The query is classified into an intent category.
4. The query is rewritten to improve retrieval quality.
5. Relevant documents are searched from the tenant-specific vector store.
6. The retrieved documents are reranked by relevance.
7. The evidence is checked for sufficiency.
8. A reply is generated only when the answer is supported by the documents.
9. If grounding is weak or missing, the workflow escalates to a human support response.

---

## Setup and run

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the app

```bash
uvicorn main:app --reload
```

Or run it directly from the repository root with the project entrypoint.

### API example

Example request:

```http
POST /api/v1/ask
Authorization: Bearer demo-tenant
Content-Type: application/json
```

```json
{
  "message": "Can I return my laptop after 20 days?",
  "conversation_id": "conv_123"
}
```

---

## What will be done in the future

### Short-term improvements

- improve the intent classifier with stronger LLM-based routing
- add a more robust query rewriter using the actual retrieved evidence
- add a dedicated `answer generation` model flow with structured validation
- enhance reranking logic and scoring for better retrieval precision
- add richer logging and request tracing for debugging support flows

### Medium-term improvements

- add persistent conversation memory and session history
- support multiple tenants with cleaner isolation and permissions
- add a frontend dashboard or admin console for support teams
- store API usage, escalation outcomes, and answer quality metrics
- improve document ingestion for more file formats and updated company policies

### Long-term goals

- integrate a production-grade LLM provider with safer evaluation and cost controls
- add human-in-the-loop escalation workflows and ticket creation
- deploy the system in Docker/Kubernetes with monitoring and CI/CD
- add metrics, alerts, and quality evaluation for answer reliability
- expand support to multilingual user requests and more complex support cases

---

## Current status

This project is already working as a functional prototype for a grounded customer support assistant. It demonstrates the key pattern of:

- document-based retrieval
- LangGraph orchestration
- evidence-based answer generation
- guardrail enforcement
- tenant-aware support handling

It is a strong foundation for a production-ready customer support AI system, with the next steps focused on quality, reliability, monitoring, and operational deployment.

---

## Notes

The project currently uses a local deterministic embedding strategy and FAISS for offline retrieval, which makes it easier to run in local environments without external API dependencies. Future work can add more advanced embedding providers and stronger production monitoring when the system is ready for wider deployment.