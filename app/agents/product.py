from app.graph.state import SupportState
from app.llm import chatModel

def product(state: SupportState):

    query = state['query']
    context = state['retrieved_docs']

    prompt = f"""You are the Product Information Support Agent.

Your responsibility is to answer questions about:
- product specifications
- product features
- compatibility
- dimensions
- materials
- availability
- usage
- product variants

Use ONLY information present in the retrieved company knowledge.

Never invent:
- specifications
- features
- prices
- compatibility
- availability
- product capabilities

If the information cannot be verified from the retrieved knowledge, return:

INSUFFICIENT_EVIDENCE

Customer Query:
{query}

Relevant Company Knowledge:
{context}"""

    output = chatModel.invoke(prompt).content

    return {'retrieved_docs': output}