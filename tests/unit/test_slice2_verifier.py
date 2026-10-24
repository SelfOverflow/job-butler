import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx

from src.ingestion.verifier import Liveness, verify, workday_cxs_url

ASHBY = "https://jobs.ashbyhq.com/hooli/1234-abcd"
WORKDAY = "https://hooli.wd5.myworkdayjobs.com/en-US/External/job/Bengaluru/Senior-Engineer_R123"
WORKDAY_CXS = (
    "https://hooli.wd5.myworkdayjobs.com/wday/cxs/hooli/External/job/Bengaluru/Senior-Engineer_R123"
)
GREENHOUSE = "https://boards.greenhouse.io/hooli/jobs/42"


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with respx.mock, httpx.Client() as c:
        yield c


def _ashby_page(app_data: dict[str, Any]) -> str:
    return f"<html><script>window.__appData = {json.dumps(app_data)};</script></html>"


def test_deep_ats_verifier_ashby_closed_posting(client: httpx.Client) -> None:
    respx.get(ASHBY).respond(200, html=_ashby_page({"posting": None, "jobBoard": {"id": 1}}))
    assert verify(ASHBY, client) == Liveness("closed", "ashby: posting is null")


def test_ashby_missing_job_board_is_closed(client: httpx.Client) -> None:
    respx.get(ASHBY).respond(200, html=_ashby_page({"posting": {"id": 9}, "jobBoard": None}))
    assert verify(ASHBY, client).status == "closed"


def test_ashby_live_posting(client: httpx.Client) -> None:
    respx.get(ASHBY).respond(200, html=_ashby_page({"posting": {"id": 9}, "jobBoard": {"id": 1}}))
    assert verify(ASHBY, client) == Liveness("live", "ashby: posting present")


def test_workday_cxs_url() -> None:
    assert workday_cxs_url(WORKDAY) == WORKDAY_CXS
    no_locale = "https://hooli.wd1.myworkdayjobs.com/Careers/job/Remote/Eng_R1"
    assert workday_cxs_url(no_locale) == (
        "https://hooli.wd1.myworkdayjobs.com/wday/cxs/hooli/Careers/job/Remote/Eng_R1"
    )


def test_deep_ats_verifier_workday_closed_posting(client: httpx.Client) -> None:
    respx.get(WORKDAY_CXS).respond(200, json={"jobPostingInfo": {"postingAvailable": False}})
    assert verify(WORKDAY, client) == Liveness("closed", "workday: postingAvailable is false")


def test_workday_live_posting(client: httpx.Client) -> None:
    respx.get(WORKDAY_CXS).respond(200, json={"jobPostingInfo": {"postingAvailable": True}})
    assert verify(WORKDAY, client).status == "live"


def test_workday_payload_without_flag_is_unknown(client: httpx.Client) -> None:
    respx.get(WORKDAY_CXS).respond(200, json={"something": "else"})
    assert verify(WORKDAY, client).status == "unknown"


@pytest.mark.parametrize("status", [404, 410])
def test_gone_status_codes_are_closed(client: httpx.Client, status: int) -> None:
    respx.get(GREENHOUSE).respond(status)
    assert verify(GREENHOUSE, client) == Liveness("closed", f"http {status}")


@pytest.mark.parametrize(
    "marker",
    [
        "Sorry, this job is no longer available.",
        "This position has been filled.",
        "This position has been closed.",
        "We are no longer accepting applications for this role.",
        "The job you are looking for is no longer open.",
        "This job posting has expired.",
        "This job is not active.",
        "This job is not published.",
        "Job not found.",
        "Sorry, we couldn't find anything here",
        "The job posting you're looking for might have closed, or it has been removed.",
    ],
)
def test_expired_markers_are_closed(client: httpx.Client, marker: str) -> None:
    respx.get(GREENHOUSE).respond(200, html=f"<html><body><h1>{marker}</h1></body></html>")
    assert verify(GREENHOUSE, client).status == "closed"


def test_greenhouse_error_redirect_is_closed(client: httpx.Client) -> None:
    board = "https://boards.greenhouse.io/hooli?error=true"
    respx.get(GREENHOUSE).respond(302, headers={"Location": board})
    respx.get(board).respond(200, html="<html>Open roles</html>")
    assert verify(GREENHOUSE, client) == Liveness("closed", "redirected to job board (error=true)")


def test_clean_page_is_live(client: httpx.Client) -> None:
    respx.get(GREENHOUSE).respond(
        200, html="<html><h1>Senior Engineer</h1><form>Apply</form></html>"
    )
    assert verify(GREENHOUSE, client) == Liveness("live", "no expiry markers")


def test_transient_failures_are_unknown(client: httpx.Client) -> None:
    respx.get(GREENHOUSE).respond(503)
    assert verify(GREENHOUSE, client) == Liveness("unknown", "http 503")
    respx.get(ASHBY).mock(side_effect=httpx.ConnectTimeout("timed out"))
    assert verify(ASHBY, client).status == "unknown"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<html>This job is no longer available</html>", "closed"),  # no __appData: generic check
        ("<script>window.__appData = {broken;</script>", "live"),  # unparseable: generic check
        (_ashby_page({"organization": "hooli"}), "live"),  # neither key present: generic check
    ],
)
def test_ashby_falls_back_to_generic_checks(client: httpx.Client, html: str, expected: str) -> None:
    respx.get(ASHBY).respond(200, html=html)
    assert verify(ASHBY, client).status == expected


def test_workday_edge_cases(client: httpx.Client) -> None:
    bad = "https://hooli.wd5.myworkdayjobs.com/en-US"
    assert verify(bad, client).status == "unknown"

    route = respx.get(WORKDAY_CXS)
    route.respond(404)
    assert verify(WORKDAY, client) == Liveness("closed", "http 404")
    route.respond(200, text="<html>not json</html>")
    assert verify(WORKDAY, client) == Liveness("unknown", "workday: response is not JSON")
    route.respond(200, json={"items": [{"meta": 1}, {"info": {"postingAvailable": False}}]})
    assert verify(WORKDAY, client).status == "closed"
