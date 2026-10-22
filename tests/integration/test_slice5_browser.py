from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from playwright.sync_api import Page

from src.agents.navigator.browser import BrowserBusyError, browser_page
from src.agents.navigator.field_mapper import map_fields
from src.agents.navigator.form_inspector import fill_form, inspect_form
from src.agents.tailor.runner import artifact_paths
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile
from tests.mock_ats import MockATS, mock_ats

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


@pytest.fixture(scope="module")
def ats() -> Iterator[MockATS]:
    with mock_ats() as server:
        yield server


@pytest.fixture
def page(ats: MockATS) -> Iterator[Page]:
    with browser_page() as p:
        p.goto(ats.url("greenhouse_apply.html"))
        yield p


def test_inspect_form_reads_labels_kinds_required_and_options(page: Page) -> None:
    fields = inspect_form(page)
    summary = [(f.label, f.kind, f.required, f.options) for f in fields]
    assert summary == [
        ("First Name", "text", True, ()),
        ("Last Name", "text", True, ()),
        ("Email", "email", True, ()),
        ("Phone", "tel", False, ()),
        ("Resume/CV", "file", True, ()),
        ("Cover Letter", "file", False, ()),
        ("LinkedIn Profile", "url", False, ()),
        ("Are you authorized to work in the US?", "select", True, ("Select...", "Yes", "No")),
        ("Do you require sponsorship?", "radio", True, ("Yes", "No")),
        ("Why do you want to work at Hooli?", "textarea", True, ()),
        ("Gender", "select", False, ("Decline to self-identify", "Male", "Female")),
        ("I agree to the privacy policy", "checkbox", True, ()),
    ]  # honeypot and hidden token are excluded
    assert all(f.selector for f in fields)


def test_fill_form_applies_the_plan(page: Page, tmp_path: Path) -> None:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    profile = CandidateProfile.model_validate(raw)
    artifacts = artifact_paths(tmp_path, "job_1234abcd")
    artifacts.resume.parent.mkdir(parents=True)
    artifacts.resume.write_bytes(b"%PDF-1.7 resume")
    artifacts.cover_pdf.parent.mkdir(parents=True)
    artifacts.cover_pdf.write_bytes(b"%PDF-1.7 cover")

    plan = map_fields(inspect_form(page), profile, artifacts, {})
    fill_form(page, plan)

    assert page.input_value("#first_name") == "Jane"
    assert page.input_value("#email") == "jane.doe@example.com"
    assert page.input_value("#linkedin") == "https://www.linkedin.com/in/janedoe"
    assert page.input_value("#authorized") == "1"  # "Yes" option
    assert page.is_checked('input[name="sponsorship"][value="no"]')
    assert page.eval_on_selector("#resume", "el => el.files[0].name") == "job_1234abcd_resume.pdf"
    assert (
        page.eval_on_selector("#cover_letter", "el => el.files[0].name") == "job_1234abcd_cover.pdf"
    )
    # Never guessed: the free-text question, the consent box, and the EEO question stay untouched.
    assert page.input_value("#why") == ""
    assert not page.is_checked("#privacy")
    assert page.input_value("#gender") == ""
    assert sorted(f.label for f in plan.unanswered) == [
        "I agree to the privacy policy",
        "Why do you want to work at Hooli?",
    ]


def test_browser_is_closed_even_when_the_block_raises(ats: MockATS) -> None:
    captured: list[Page] = []
    with pytest.raises(RuntimeError), browser_page() as page:
        captured.append(page)
        page.goto(ats.url("greenhouse_apply.html"))
        raise RuntimeError("boom")
    assert captured[0].is_closed()


def test_only_one_browser_at_a_time(ats: MockATS) -> None:
    with browser_page(), pytest.raises(BrowserBusyError), browser_page():
        pass
    with browser_page() as again:  # lock released afterwards
        again.goto(ats.url("greenhouse_apply.html"))
