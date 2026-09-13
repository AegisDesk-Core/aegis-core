INTENT_CLASSIFIER_PROMPT = """Classify the customer message into exactly one of: refund, shipping, product, or other.
Return only one category and nothing else.
Do not answer the question.
If ambiguous, return other.

Customer message:
{query}

Category:"""

QUERY_REWRITER_PROMPT = """Rewrite the customer message into a short, retrieval-friendly search query.
Preserve meaning and product names, dates, and conditions.
Do not invent facts, do not answer the question, and do not add policy details.
Return only the rewritten query.

Customer message:
{query}
Intent:
{intent}

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
Never invent policies, fees, dates, shipping times, product specs, pricing, availability, or eligibility.
If the evidence is insufficient, do not guess.
Keep the answer concise, helpful, and grounded in the documented policy.

Query:
{query}
Intent:
{intent}
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
