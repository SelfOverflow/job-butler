"""Test doubles shared across suites (no real LLM calls in tests)."""

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    """Returns canned responses (or computes them from the prompt) and records prompts."""

    def __init__(self, respond: Callable[[str, type[BaseModel]], BaseModel]) -> None:
        self._respond = respond
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, schema: type[T]) -> T:
        self.prompts.append(prompt)
        result = self._respond(prompt, schema)
        assert isinstance(result, schema)
        return result


def template_summary() -> BaseModel:
    """A summary grounded in the template profile, for fakes answering SummaryDraft."""
    from src.agents.tailor.summary import SummaryDraft

    return SummaryDraft(
        text="Senior Backend Engineer who architected an event-driven ingestion pipeline "
        "handling 25,000 requests per second with 99.99% uptime."
    )

