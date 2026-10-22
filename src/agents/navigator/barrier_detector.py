"""Detect application blockers that require a human: accounts, CAPTCHAs, 2FA.

Works on a page's URL and HTML so it is testable without a browser. Invisible
reCAPTCHA v3 (script-only or data-size="invisible") is common on direct ATS
forms and does not block submission, so only visible challenge widgets count.
"""

import re
from enum import StrEnum
from urllib.parse import urlsplit

from src.ingestion.base import html_to_text


class Barrier(StrEnum):
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    TWO_FACTOR_REQUIRED = "TWO_FACTOR_REQUIRED"
    ACCOUNT_CREATION_REQUIRED = "ACCOUNT_CREATION_REQUIRED"


# Portals that always require a candidate account before applying.
ACCOUNT_PORTALS = (
    "myworkdayjobs.com",
    "taleo.net",
    "icims.com",
    "successfactors.com",
    "successfactors.eu",
    "brassring.com",
    "oraclecloud.com",
)
_CAPTCHA_WIDGET = re.compile(
    r"<[^>]*class=\"[^\"]*\b(?:g-recaptcha|h-captcha|cf-turnstile)\b[^\"]*\"[^>]*>", re.IGNORECASE
)
_CAPTCHA_FRAME = re.compile(
    r"<iframe[^>]*src=\"[^\"]*(?:recaptcha/api2/anchor|hcaptcha\.com/captcha|challenges\.cloudflare\.com)",
    re.IGNORECASE,
)
_SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_TWO_FACTOR = re.compile(
    r"verification code|enter the code|one-time pass(?:code|word)|two-factor|2fa\b", re.IGNORECASE
)
_ACCOUNT = re.compile(
    r"sign in to (?:apply|continue)|log ?in to (?:apply|continue)|create an account|"
    r"create your (?:candidate )?(?:account|profile)",
    re.IGNORECASE,
)


def detect_barrier(url: str, html: str) -> Barrier | None:
    visible_html = _SCRIPT_OR_STYLE.sub(" ", html)
    widgets = [w for w in _CAPTCHA_WIDGET.findall(visible_html) if "invisible" not in w.lower()]
    if widgets or _CAPTCHA_FRAME.search(visible_html):
        return Barrier.CAPTCHA_DETECTED

    text = html_to_text(visible_html)
    if 'autocomplete="one-time-code"' in visible_html.lower() or _TWO_FACTOR.search(text):
        return Barrier.TWO_FACTOR_REQUIRED

    host = urlsplit(url).hostname or ""
    if any(host == p or host.endswith("." + p) for p in ACCOUNT_PORTALS):
        return Barrier.ACCOUNT_CREATION_REQUIRED
    if re.search(r"<input[^>]*type=\"password\"", visible_html, re.IGNORECASE) or _ACCOUNT.search(
        text
    ):
        return Barrier.ACCOUNT_CREATION_REQUIRED
    return None
