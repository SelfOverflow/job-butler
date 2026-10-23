from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors
from pydantic import BaseModel

from src.agents.llm import GeminiClient, LLMError, make_llm
from src.config.settings import Settings


class Answer(BaseModel):
    keywords: list[str]


class StubInteractions:
    def __init__(self, output_text: str = "", error: Exception | None = None) -> None:
        self.output_text, self.error = output_text, error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


def _gemini(interactions: StubInteractions) -> GeminiClient:
    return GeminiClient("key", "gemini-test", sdk=SimpleNamespace(interactions=interactions))


def test_gemini_requests_json_matching_the_schema() -> None:
    stub = StubInteractions('{"keywords": ["python", "react"]}')
    result = _gemini(stub).generate_json("Extract keywords", Answer)

    assert result == Answer(keywords=["python", "react"])
    [call] = stub.calls
    assert call["model"] == "gemini-test"
    assert call["input"] == "Extract keywords"
    assert call["response_format"] == {
        "mime_type": "application/json",
        "schema": Answer.model_json_schema(),
    }


@pytest.mark.parametrize("output", ["not json", '{"keywords": "python"}', ""])
def test_gemini_invalid_output_raises_llm_error(output: str) -> None:
    with pytest.raises(LLMError, match="did not match"):
        _gemini(StubInteractions(output)).generate_json("p", Answer)


def test_gemini_api_errors_are_wrapped() -> None:
    error = errors.APIError(429, {"error": {"message": "quota exceeded"}})
    with pytest.raises(LLMError, match="Gemini request failed"):
        _gemini(StubInteractions(error=error)).generate_json("p", Answer)


def test_interactions_timeouts_and_connection_errors_are_wrapped() -> None:
    # Interactions API errors are not subclasses of errors.APIError.
    from google.genai._gaos.lib.compat_errors import APITimeoutError

    error = APITimeoutError(request=None)  # type: ignore[arg-type]
    with pytest.raises(LLMError, match="Gemini request failed"):
        _gemini(StubInteractions(error=error)).generate_json("p", Answer)


def test_gemini_client_sets_a_request_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr("src.agents.llm.genai.Client", lambda **kw: seen.update(kw))
    GeminiClient("key", "gemini-test")
    assert seen["http_options"].timeout == 120_000


def test_make_llm_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        make_llm(Settings(_env_file=None))


def test_make_llm_uses_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    llm = make_llm(Settings(_env_file=None))
    assert isinstance(llm, GeminiClient) and llm.model == "gemini-3.5-flash-lite"
    assert Settings(_env_file=None, gemini_model="x").gemini_model == "x"


def test_default_model() -> None:
    assert Settings(_env_file=None).gemini_model == "gemini-3.8-flash"
