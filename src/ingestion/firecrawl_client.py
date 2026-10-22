"""Firecrawl /v2/search with a daily credit ceiling and a 12-hour result cache.

State lives as small JSON files under `state_dir` so the CLI and the background
worker share one budget and cache. Cached results are served even when the
budget is exhausted.
"""

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

API = "https://api.firecrawl.dev/v2/search"
TIMEOUT = 60.0


class FirecrawlError(Exception):
    pass


class BudgetExceededError(FirecrawlError):
    pass


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    description: str


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FirecrawlClient:
    def __init__(
        self,
        api_key: str | None,
        http: httpx.Client,
        state_dir: Path,
        daily_credits: int,
        cache_ttl: timedelta = timedelta(hours=12),
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        if not api_key:
            raise FirecrawlError("FIRECRAWL_API_KEY is not set")
        self._api_key, self._http, self._clock = api_key, http, clock
        self._daily_credits, self._cache_ttl = daily_credits, cache_ttl
        self._cache_dir = state_dir / "cache"
        self._budget_file = state_dir / "budget.json"

    def search(self, query: str, limit: int = 10, tbs: str | None = None) -> list[SearchResult]:
        body: dict[str, Any] = {"query": query, "limit": limit}
        if tbs:
            body["tbs"] = tbs
        cache_file = (
            self._cache_dir / f"{hashlib.sha256(json.dumps(body).encode()).hexdigest()}.json"
        )
        if (cached := self._read_cache(cache_file)) is not None:
            return cached
        if self.credits_used_today() >= self._daily_credits:
            raise BudgetExceededError(
                f"Daily Firecrawl budget of {self._daily_credits} credits used"
            )

        try:
            response = self._http.post(
                API,
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise FirecrawlError(f"Firecrawl search failed: {exc}") from exc
        if not payload.get("success"):
            raise FirecrawlError(
                f"Firecrawl search failed: {payload.get('error', 'unknown error')}"
            )

        self._add_credits(int(payload.get("creditsUsed", limit)))
        results = [
            SearchResult(
                url=r["url"], title=r.get("title", ""), description=r.get("description", "")
            )
            for r in payload.get("data", {}).get("web", [])
        ]
        _write_json(
            cache_file,
            {"fetched_at": self._clock().isoformat(), "results": [asdict(r) for r in results]},
        )
        return results

    def credits_used_today(self) -> int:
        state = _read_json(self._budget_file)
        return int(state["credits_used"]) if state.get("date") == self._today() else 0

    def _add_credits(self, credits: int) -> None:
        _write_json(
            self._budget_file,
            {"date": self._today(), "credits_used": self.credits_used_today() + credits},
        )

    def _today(self) -> str:
        return self._clock().date().isoformat()

    def _read_cache(self, path: Path) -> list[SearchResult] | None:
        entry = _read_json(path)
        if (
            not entry
            or self._clock() - datetime.fromisoformat(entry["fetched_at"]) > self._cache_ttl
        ):
            return None
        return [SearchResult(**r) for r in entry["results"]]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write via temp file + rename so a concurrent reader never sees a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)
