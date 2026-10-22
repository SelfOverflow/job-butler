"""Deep liveness checks for job posting URLs.

Returns `unknown` (not `closed`) for transient failures so a flaky network never
purges a real job. Only explicit evidence -- 404/410, ATS payload flags, or
expiry wording -- marks a posting closed.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx

TIMEOUT = 15.0
_EXPIRED = re.compile(
    r"no longer (available|open|accepting applications)"
    r"|position has been filled"
    r"|posting has expired"
    r"|job (is|has been) closed",
    re.IGNORECASE,
)
_ASHBY_APP_DATA = re.compile(r"window\.__appData\s*=\s*(\{.*?\});\s*</script>", re.DOTALL)
_LOCALE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


@dataclass(frozen=True)
class Liveness:
    status: Literal["live", "closed", "unknown"]
    reason: str


def verify(url: str, client: httpx.Client) -> Liveness:
    host = urlsplit(url).hostname or ""
    try:
        if host.endswith(".myworkdayjobs.com"):
            return _verify_workday(url, client)
        response = client.get(url, follow_redirects=True, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        return Liveness("unknown", f"request failed: {type(exc).__name__}")

    if (status := _status_verdict(response)) is not None:
        return status
    if response.url.params.get("error") == "true":  # Greenhouse bounces closed jobs to the board.
        return Liveness("closed", "redirected to job board (error=true)")
    if host == "jobs.ashbyhq.com" and (ashby := _verify_ashby(response.text)) is not None:
        return ashby
    if match := _EXPIRED.search(response.text):
        return Liveness("closed", f"expiry marker: {match.group(0)!r}")
    return Liveness("live", "no expiry markers")


def _status_verdict(response: httpx.Response) -> Liveness | None:
    if response.status_code in (404, 410):
        return Liveness("closed", f"http {response.status_code}")
    if response.status_code >= 400:
        return Liveness("unknown", f"http {response.status_code}")
    return None


def _verify_ashby(html: str) -> Liveness | None:
    """Inspect Ashby's embedded `window.__appData`; None if it is absent or unparseable."""
    match = _ASHBY_APP_DATA.search(html)
    if match is None:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    for key in ("posting", "jobBoard"):
        if key in data and data[key] is None:
            return Liveness("closed", f"ashby: {key} is null")
    if data.get("posting"):
        return Liveness("live", "ashby: posting present")
    return None


def workday_cxs_url(url: str) -> str:
    """Map a public Workday job URL to its JSON (CXS) endpoint."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    segments = [s for s in parts.path.split("/") if s]
    if segments and _LOCALE.match(segments[0]):
        segments = segments[1:]
    if len(segments) < 2:
        raise ValueError(f"Not a Workday job URL: {url}")
    tenant, site, rest = host.split(".")[0], segments[0], "/".join(segments[1:])
    return f"{parts.scheme}://{host}/wday/cxs/{tenant}/{site}/{rest}"


def _verify_workday(url: str, client: httpx.Client) -> Liveness:
    try:
        api_url = workday_cxs_url(url)
    except ValueError as exc:
        return Liveness("unknown", str(exc))
    response = client.get(api_url, headers={"Accept": "application/json"}, timeout=TIMEOUT)
    if (status := _status_verdict(response)) is not None:
        return status
    try:
        flag = _find_key(response.json(), "postingAvailable")
    except json.JSONDecodeError:
        return Liveness("unknown", "workday: response is not JSON")
    if flag is True:
        return Liveness("live", "workday: postingAvailable is true")
    if flag is False:
        return Liveness("closed", "workday: postingAvailable is false")
    return Liveness("unknown", "workday: postingAvailable missing")


def _find_key(node: Any, key: str) -> Any:
    """Depth-first search for `key` in nested JSON; None if absent."""
    if isinstance(node, dict):
        if key in node:
            return node[key]
        children: list[Any] = list(node.values())
    elif isinstance(node, list):
        children = node
    else:
        return None
    for child in children:
        if (found := _find_key(child, key)) is not None:
            return found
    return None
