from app.graph.state import SupportState
from app.llm import chatModel

def shipping(state: SupportState):

    query = state['query']
    context = state['retrieved_docs']

    prompt = f"""You are the Shipping Support Agent.

Your responsibility is to handle customer questions related to:
- shipping
- delivery
- order tracking
- delivery time
- shipping charges
- delivery locations
- delayed shipments

Use ONLY the retrieved company information.

Never invent:
- delivery dates
- tracking information
- shipping charges
- delivery locations
- courier information
- estimated delivery times

If the retrieved knowledge does not contain enough evidence, return:

INSUFFICIENT_EVIDENCE

Customer Query:
{query}

Relevant Company Knowledge:
{context}"""

    output = chatModel.invoke(prompt).content

    return {'retrieved_docs': output}