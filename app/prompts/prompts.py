INTENT_CLASSIFIER_PROMPT = """Classify the customer message into exactly one of: refund, shipping, product, or other.
Return only one category and nothing else.
Do not answer the question.
If ambiguous, return other.

Customer message:
{query}

Category:"""

QUERY_REWRITER_PROMPT = """Rewrite the customer message into a short, retrieval-friendly search query.
Preserve meaning and product names, dates, and conditions.
Use recent conversation context to resolve references such as "it" or "that".
Do not invent facts, do not answer the question, and do not add policy details.
Return only the rewritten query.

Customer message:
{query}
Intent:
{intent}
Recent conversation:
{conversation_history}

Rewritten query:"""

EVIDENCE_CHECKER_PROMPT = """Determine whether the retrieved company documents are sufficient to answer the customer safely.
Use only the provided evidence.
If required conditions, dates, exceptions, or product details are missing, decide insufficient.
If evidence is contradictory, decide insufficient.
Return JSON with keys: sufficient, reason, missing_info.

Query:
{query}

Evidence:
{evidence}

JSON:"""

ANSWER_GENERATOR_PROMPT = """Answer only from verified company evidence.
You are a professional customer-support agent. Use the conversation to understand
follow-up questions, but treat the evidence below as the only source of truth.
Never invent policies, fees, dates, shipping times, product specs, pricing,
availability, or eligibility. Refuse unsupported answers by setting needs_human
to true and keeping the answer brief. Keep the answer under 120 words.

Every factual claim must be marked supported=true and cite at least one exact
document/page from the evidence. Return citations only for the source references
provided below. If the evidence is contradictory or incomplete, set needs_human
to true. Always include at least one response citation and at least one claim.
Do not leave citations or claims empty. Return the required structured schema.

Query:
{query}
Intent:
{intent}
Conversation history:
{conversation_history}
Evidence:
{evidence}

Answer:"""

GROUNDING_CHECKER_PROMPT = """Check every factual claim in the answer against the provided evidence.
Return JSON with keys: grounded, confidence, reason.
Grounded must be true only if every factual claim matches the evidence.

Query:
{query}
Evidence:
{evidence}
Answer:
{answer}

JSON:"""

ESCALATION_PROMPT = """Provide a very short, polite escalation message for a human support representative.
Do not guess or invent policy information.
Customer query: {query}
Reason: {reason}

Message:"""
