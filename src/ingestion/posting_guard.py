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

_ATTR_RE = re.compile(
    r"([^\s=/\"'>]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>\"']+)))?"
)
_TAG_RE = re.compile(r"<(/?)([a-zA-Z][\w:-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.DOTALL)

_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none"
    r"|visibility\s*:\s*hidden"
    r"|opacity\s*:\s*0(?![.\d]*[1-9])"
    r"|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?"
    r"|color\s*:\s*transparent"
    r"|clip\s*:\s*rect\(\s*0"
    r"|clip-path\s*:\s*inset\(\s*100%"
    r"|(?:left|top|text-indent)\s*:\s*-\d{4,}px",
    re.IGNORECASE,
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

_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}


def _is_hidden(raw_attrs: str) -> bool:
    attrs: dict[str, str] = {}
    for m in _ATTR_RE.finditer(raw_attrs):
        val = (
            m.group(2)
            if m.group(2) is not None
            else m.group(3)
            if m.group(3) is not None
            else (m.group(4) or "")
        )
        attrs[m.group(1).lower()] = val
    if "hidden" in attrs or attrs.get("aria-hidden", "").strip().lower() == "true":
        return True
    return bool(_HIDDEN_STYLE.search(attrs.get("style", "")))


def clean_html_payload(markup: str) -> str:
    """Strip scripts, styles, SVG, hidden DOM blocks, and invisible characters from HTML."""
    no_scripts = _DROP_TAGS_RE.sub("", markup)
    visible: list[str] = []
    pos = 0
    stack: list[str] = []
    hidden_depth = 0

    for m in _TAG_RE.finditer(no_scripts):
        if hidden_depth == 0:
            visible.append(no_scripts[pos:m.start()])
        pos = m.end()

        closing, tag_name, raw_attrs = m.group(1), m.group(2).lower(), m.group(3)
        if not closing:
            hidden = _is_hidden(raw_attrs)
            if hidden or hidden_depth > 0:
                hidden_depth += 1
            else:
                visible.append(m.group(0))
            if tag_name not in _VOID_TAGS:
                stack.append(tag_name)
        else:
            if hidden_depth > 0:
                hidden_depth -= 1
            else:
                visible.append(m.group(0))
            if tag_name in stack:
                while stack and stack.pop() != tag_name:
                    pass

    if hidden_depth == 0:
        visible.append(no_scripts[pos:])

    text = "".join(visible)
    return _INVISIBLE_RE.sub("", text)


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
