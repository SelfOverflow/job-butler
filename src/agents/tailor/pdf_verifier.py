"""ATS text-layer verification: what a resume parser would actually read."""

import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

import pypdf
from pypdf.errors import PyPdfError

from src.ingestion.base import contains_phrase, words
from src.profile.models import CandidateProfile

_GLITCH = re.compile(r"�|\(cid:\d+\)")


@dataclass
class PdfReport:
    pages: int
    checks: dict[str, bool]
    problems: list[str]
    keywords_matched: list[str] = field(default_factory=list)
    keywords_missing: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


def _extract(pdf: bytes) -> tuple[int, str]:
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf))
        return len(reader.pages), "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PyPdfError, ValueError):
        return 0, ""


def extract_text(pdf: bytes) -> str:
    """The text layer an ATS parses."""
    return _extract(pdf)[1]


def verify_pdf(
    pdf: bytes, profile: CandidateProfile, keywords: Sequence[str], max_pages: int
) -> PdfReport:
    pages, text = _extract(pdf)
    info = profile.personal_info
    compact = re.sub(r"\s+", "", text)  # URLs/phones may wrap across lines.
    checks = {
        "text": bool(text.strip()) and not _GLITCH.search(text),
        "linkedin": info.links.linkedin in compact,
        "contact": info.email in compact and re.sub(r"\s+", "", info.phone) in compact,
        "pages": 0 < pages <= max_pages,
    }
    messages = {
        "text": "Text layer is empty or contains replacement glyphs",
        "linkedin": f"LinkedIn URL not found verbatim: {info.links.linkedin}",
        "contact": "Email or phone missing from the text layer",
        "pages": f"{pages} page(s), budget {max_pages}",
    }
    text_words = words(text)
    matched = [k for k in keywords if contains_phrase(text_words, words(k))]
    return PdfReport(
        pages=pages,
        checks=checks,
        problems=[messages[name] for name, ok in checks.items() if not ok],
        keywords_matched=matched,
        keywords_missing=[k for k in keywords if k not in matched],
    )
