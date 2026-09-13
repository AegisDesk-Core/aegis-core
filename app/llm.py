from typing import Any

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:  # pragma: no cover - fallback for missing optional dependency
    ChatGoogleGenerativeAI = None


class _FallbackModel:
    def __init__(self, name: str):
        self.name = name

    def invoke(self, prompt: Any):
        if isinstance(prompt, str):
            return prompt
        return str(prompt)

    def with_structured_output(self, model_type: Any):
        return self


if ChatGoogleGenerativeAI is not None:
    try:
        from app.config import get_env
        api_key = get_env("GEMINI_API_KEY")
        chatModel = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", api_key=api_key) if api_key else _FallbackModel("gemini-fallback")
    except Exception:
        chatModel = _FallbackModel("gemini-fallback")
else:
    chatModel = _FallbackModel("gemini-fallback")

structModel = chatModel
scoreModel = chatModel