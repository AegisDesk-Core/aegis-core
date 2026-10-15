import json
from typing import Any

from pydantic import BaseModel, Field

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:  # pragma: no cover - fallback for missing optional dependency
    ChatGoogleGenerativeAI = None

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover - optional until the Google provider is selected
    genai = None
    types = None

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - fallback for missing optional dependency
    ChatOpenAI = None


DEFAULT_GOOGLE_MODEL = "gemini-3.5-flash-lite"


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
        model_name = get_env("LLM_MODEL") or DEFAULT_GOOGLE_MODEL
        chatModel = ChatGoogleGenerativeAI(model=model_name, api_key=api_key) if api_key else _FallbackModel("gemini-fallback")
    except Exception:
        chatModel = _FallbackModel("gemini-fallback")
else:
    chatModel = _FallbackModel("gemini-fallback")

structModel = chatModel
scoreModel = chatModel


class Citation(BaseModel):
    document: str = Field(..., min_length=1)
    page: int = Field(..., ge=1)


class SupportedClaim(BaseModel):
    claim: str = Field(..., min_length=1)
    supported: bool
    citations: list[Citation] = Field(..., min_length=1)


class AnswerResponse(BaseModel):
    answer: str = Field(..., min_length=1, max_length=1200)
    confidence: float = Field(..., ge=0.0, le=1.0)
    citations: list[Citation] = Field(..., min_length=1)
    needs_human: bool = False
    claims: list[SupportedClaim] = Field(..., min_length=1)


class _GoogleAnswerModel:
    def __init__(self, model_name: str, api_key: str):
        if genai is None or types is None:
            raise RuntimeError("Install google-genai to use the Google provider.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def invoke(self, prompt: str) -> AnswerResponse:
        chat = self.client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AnswerResponse,
                max_output_tokens=2000,
            ),
        )
        response = chat.send_message(prompt)
        if isinstance(response.parsed, AnswerResponse):
            return response.parsed
        if response.parsed is not None:
            return AnswerResponse.model_validate(response.parsed)
        if response.text:
            return AnswerResponse.model_validate(json.loads(response.text))
        raise ValueError("Google returned no parsed answer or response text.")


def get_answer_model():
    """Create the configured production model for grounded answer generation."""
    from app.config import get_env

    provider = (get_env("LLM_PROVIDER") or "google").strip().lower()
    model_name = get_env("LLM_MODEL")

    if provider == "google":
        api_key = get_env("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for the Google provider.")
        return _GoogleAnswerModel(model_name or DEFAULT_GOOGLE_MODEL, api_key)
    elif provider == "openai":
        if ChatOpenAI is None:
            raise RuntimeError("Install langchain-openai to use the OpenAI provider.")
        api_key = get_env("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI provider.")
        model = ChatOpenAI(
            model=model_name or "gpt-4o-mini",
            api_key=api_key,
            temperature=0,
            max_tokens=500,
        )
    else:
        raise RuntimeError("LLM_PROVIDER must be either 'google' or 'openai'.")

    return model.with_structured_output(AnswerResponse, method="json_schema")