"""Source-agnostic job posting DTO shared by every ingestion adapter."""

import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from src.ingestion.posting_guard import clean_html_payload, sanitize_posting_text

# progress(stage, done, total, detail): called with done=0 when a stage starts and
# after each completed step, so callers can render progress without coupling.
ProgressFn = Callable[[str, int, int, str], None]


def no_progress(stage: str, done: int, total: int, detail: str) -> None:
    pass


@dataclass(frozen=True)
class RawJobPosting:
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str  # Adapter name, e.g. "greenhouse", "lever", "firecrawl".
    posted_at: datetime | None = None

    def __post_init__(self) -> None:
        # Sources are sloppy ("GovTech "); trimming keeps dedupe keys and display clean.
        for name in ("title", "company", "location"):
            object.__setattr__(self, name, getattr(self, name).strip())


def words(text: str) -> tuple[str, ...]:
    """Case- and punctuation-insensitive word tuple: `"Acme, Corp."` -> `("acme", "corp")`."""
    return tuple(re.sub(r"[^\w]+", " ", text.casefold()).split())


def contains_phrase(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    """True if `needle` occurs as a contiguous run of whole words in `haystack`."""
    n = len(needle)
    if n == 0:
        return False
    if n == 1:
        return needle[0] in haystack  # C-level scan; this is the hot path in scoring.
    start = 0
    while True:  # Only compare at positions where the first word occurs.
        try:
            i = haystack.index(needle[0], start)
        except ValueError:
            return False
        if haystack[i : i + n] == needle:
            return True
        start = i + 1


def html_to_text(markup: str) -> str:
    """Plain text from (possibly entity-escaped) HTML, whitespace collapsed."""
    clean = clean_html_payload(markup)
    stripped = re.sub(r"<[^>]+>", " ", html.unescape(clean))
    return sanitize_posting_text(" ".join(html.unescape(stripped).split()))


_BLOCK_END = re.compile(r"</(p|div|h[1-6]|ul|ol|li|section|table|tr)>|<br\s*/?>", re.I)
_HEADING = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.I | re.S)
_BOLD_PARA = re.compile(r"<p[^>]*>\s*<(strong|b)>(.*?)</\1>\s*</p>", re.I | re.S)


def plain_to_markdown(text: str) -> str:
    """Normalise plain text into lines and blank-line separated paragraphs."""
    lines = [" ".join(line.split()) for line in text.replace("\xa0", " ").splitlines()]
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def html_to_markdown(markup: str) -> str:
    """Readable Markdown subset from (possibly entity-escaped) HTML.

    Keeps `## ` headings, `- ` bullets and paragraph breaks so descriptions render with
    structure; word content is identical to `html_to_text`, so scoring is unaffected.
    """
    clean = clean_html_payload(markup)
    text = html.unescape(clean).replace("\n", " ")
    text = _HEADING.sub(r"\n\n## \1\n\n", text)
    text = _BOLD_PARA.sub(r"\n\n## \2\n\n", text)
    text = re.sub(r"<li[^>]*>", "\n- ", text, flags=re.I)
    text = _BLOCK_END.sub(lambda m: "\n" if m.group(0).lower().startswith("<br") else "\n\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    md = plain_to_markdown(text)
    sanitized = sanitize_posting_text(md)
    return re.sub(r"(?m)^(- .*)\n\n(?=- )", r"\1\n", sanitized)  # Tight lists.


def to_naive_utc(moment: datetime) -> datetime:
    """Storage uses naive UTC; aware datetimes are converted, naive ones assumed UTC."""
    return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment
