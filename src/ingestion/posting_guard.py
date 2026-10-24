"""Posting guardrail: cleans invisible chars, drops hidden HTML, and blocks prompt injections."""

import re

# Invisible and tampering unicode characters
ZERO_WIDTH = "\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064"
BIDI_TAMPER = "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
BOM = "\ufeff"
SOFT_HYPHEN = "\u00ad"
INVISIBLE_CHARS = ZERO_WIDTH + BIDI_TAMPER + BOM + SOFT_HYPHEN

_INVISIBLE_RE = re.compile(f"[{re.escape(INVISIBLE_CHARS)}]")

# Tags to drop completely along with their inner content
_DROP_TAGS_RE = re.compile(
    r"<(script|style|noscript|svg|template)\b[^>]*>.*?(?:</\1\s*>|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Hidden styling and attributes
_HIDDEN_ATTR_RE = re.compile(
    r"<([a-zA-Z0-9]+)\b[^>]*\b("
    r"hidden"
    r"|aria-hidden\s*=\s*[\"']?true[\"']?"
    r"|style\s*=\s*[\"'][^\"']*(?:"
    r"display\s*:\s*none"
    r"|visibility\s*:\s*hidden"
    r"|opacity\s*:\s*0(?![.\d]*[1-9])"
    r"|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?"
    r"|color\s*:\s*transparent"
    r")[^\"']*[\"']"
    r")[^>]*>.*?(?:</\1\s*>|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Adversarial prompt-injection patterns targeting LLMs
_INJECTION_PATTERNS = [
    re.compile(r"\bignore\s+(?:all|any|the|previous|prior|above|earlier)\b", re.IGNORECASE),
    re.compile(
        r"\byou\s+are\s+(?:an?|the|now)\s+(?:ai|assistant|model|llm|language model)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(
        r"\bdo\s+not\s+follow\s+(?:earlier|previous|above|prior)\s+instructions\b", re.IGNORECASE
    ),
]


def clean_html_payload(markup: str) -> str:
    """Strip scripts, styles, SVG, hidden DOM blocks, and invisible characters from HTML."""
    no_scripts = _DROP_TAGS_RE.sub("", markup)
    no_hidden = _HIDDEN_ATTR_RE.sub("", no_scripts)
    return _INVISIBLE_RE.sub("", no_hidden)


def detect_injections(text: str) -> list[str]:
    """Detect instruction-shaped lines aimed at prompt injecting the LLM."""
    found: list[str] = []
    for line in text.splitlines():
        line_clean = line.strip()
        if any(pat.search(line_clean) for pat in _INJECTION_PATTERNS):
            found.append(line_clean)
    return found


def sanitize_posting_text(text: str) -> str:
    """Remove invisible characters and redact adversarial injection lines."""
    clean = _INVISIBLE_RE.sub("", text)
    lines = clean.splitlines()
    sanitized: list[str] = []
    for line in lines:
        if any(pat.search(line) for pat in _INJECTION_PATTERNS):
            sanitized.append("[REDACTED_INSTRUCTION]")
        else:
            sanitized.append(line)
    return "\n".join(sanitized)
