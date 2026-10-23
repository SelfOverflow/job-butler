"""Lever public postings API: api.lever.co/v0/postings/<board>?mode=json."""

from datetime import UTC, datetime
from typing import Any

import httpx

from src.ingestion.base import RawJobPosting, html_to_markdown, plain_to_markdown, to_naive_utc
from src.profile.models import WatchedCompany

API = "https://api.lever.co/v0/postings/{board}"
TIMEOUT = 30.0


def fetch_lever(company: WatchedCompany, client: httpx.Client) -> list[RawJobPosting]:
    response = client.get(API.format(board=company.board), params={"mode": "json"}, timeout=TIMEOUT)
    response.raise_for_status()
    return [_to_posting(post, company) for post in response.json()]


def _to_posting(post: dict[str, Any], company: WatchedCompany) -> RawJobPosting:
    sections = [plain_to_markdown(post.get("descriptionPlain", ""))]
    for item in post.get("lists", []):
        if heading := " ".join(item.get("text", "").split()):
            sections.append(f"## {heading}")
        sections.append(html_to_markdown(item.get("content", "")))
    sections.append(plain_to_markdown(post.get("additionalPlain", "")))
    created_ms = post.get("createdAt")
    return RawJobPosting(
        title=post["text"],
        company=company.name,
        location=post.get("categories", {}).get("location") or "",
        url=post["hostedUrl"],
        description="\n\n".join(s for s in sections if s),
        source="lever",
        posted_at=to_naive_utc(datetime.fromtimestamp(created_ms / 1000, UTC))
        if created_ms
        else None,
    )
