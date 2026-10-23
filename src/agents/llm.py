"""Provider-neutral LLM interface returning schema-validated JSON.

Agents depend only on `LLMClient`, so swapping providers (or using a fake in
tests) never touches agent code.
"""

from typing import Any, Protocol, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from src.config.settings import Settings

T = TypeVar("T", bound=BaseModel)
TIMEOUT_MS = 120_000  # A hung request must fail the run, not leave it "tailoring" forever.


class LLMError(Exception):
    pass


class LLMClient(Protocol):
    def generate_json(self, prompt: str, schema: type[T]) -> T: ...


class GeminiClient:
    """Gemini via the Interactions API with JSON output constrained to `schema`."""

    def __init__(self, api_key: str, model: str, sdk: Any = None) -> None:
        self.model = model
        self._sdk: Any = sdk or genai.Client(  # non-streaming calls only
            api_key=api_key, http_options=types.HttpOptions(timeout=TIMEOUT_MS)
        )

    def generate_json(self, prompt: str, schema: type[T]) -> T:
        try:
            interaction = self._sdk.interactions.create(
                model=self.model,
                input=prompt,
                response_format={
                    "mime_type": "application/json",
                    "schema": schema.model_json_schema(),
                },
            )
        except Exception as exc:  # SDK errors (incl. Interactions timeouts) share no base class.
            raise LLMError(f"Gemini request failed: {exc}") from exc
        try:
            return schema.model_validate_json(interaction.output_text or "")
        except ValidationError as exc:
            raise LLMError(f"Gemini output did not match {schema.__name__}: {exc}") from exc


def make_llm(settings: Settings) -> LLMClient:
    if not settings.gemini_api_key:
        raise LLMError("GEMINI_API_KEY is not set")
    return GeminiClient(settings.gemini_api_key, settings.gemini_model)
