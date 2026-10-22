import pytest

from src.agents.navigator.barrier_detector import Barrier, detect_barrier

GREENHOUSE = "https://boards.greenhouse.io/hooli/jobs/1"
FORM = """
<form id="application_form">
  <label for="first_name">First Name *</label><input id="first_name" name="first_name" required>
  <label for="resume">Resume/CV *</label><input type="file" id="resume" name="resume">
  <button type="submit">Submit Application</button>
</form>
"""


def test_plain_application_form_has_no_barrier() -> None:
    assert detect_barrier(GREENHOUSE, FORM) is None


def test_invisible_recaptcha_v3_is_not_a_barrier() -> None:
    html = FORM + '<script src="https://www.google.com/recaptcha/api.js?render=6Lc_key"></script>'
    html += '<div class="g-recaptcha" data-sitekey="k" data-size="invisible"></div>'
    assert detect_barrier(GREENHOUSE, html) is None


@pytest.mark.parametrize(
    "widget",
    [
        '<div class="g-recaptcha" data-sitekey="6Lc_key"></div>',
        '<div class="h-captcha" data-sitekey="abc"></div>',
        '<div class="cf-turnstile" data-sitekey="0x4AAA"></div>',
        '<iframe src="https://www.google.com/recaptcha/api2/anchor?k=x"></iframe>',
    ],
)
def test_barrier_detector_captcha(widget: str) -> None:
    assert detect_barrier(GREENHOUSE, FORM + widget) is Barrier.CAPTCHA_DETECTED


@pytest.mark.parametrize(
    "url",
    [
        "https://hooli.wd5.myworkdayjobs.com/en-US/External/job/Bengaluru/Engineer_R1",
        "https://hooli.taleo.net/careersection/2/jobdetail.ftl?job=1",
        "https://careers-hooli.icims.com/jobs/1/engineer/job",
        "https://career5.successfactors.eu/sfcareer/jobreqcareer?jobId=1",
    ],
)
def test_account_portals_by_host(url: str) -> None:
    assert detect_barrier(url, FORM) is Barrier.ACCOUNT_CREATION_REQUIRED


@pytest.mark.parametrize(
    "html",
    [
        '<form><input type="email" name="email"><input type="password" name="password"></form>',
        "<h1>Sign in to apply</h1><p>Use your candidate account.</p>",
        "<h2>Create an account</h2><p>to continue your application</p>",
    ],
)
def test_barrier_detector_login_prompt(html: str) -> None:
    assert (
        detect_barrier("https://jobs.example.com/apply", html) is Barrier.ACCOUNT_CREATION_REQUIRED
    )


@pytest.mark.parametrize(
    "html",
    [
        '<input name="code" autocomplete="one-time-code">',
        "<p>Enter the verification code we sent to your email.</p>",
        "<h2>Two-factor authentication</h2>",
    ],
)
def test_barrier_detector_two_factor(html: str) -> None:
    assert detect_barrier("https://jobs.example.com/apply", html) is Barrier.TWO_FACTOR_REQUIRED


def test_captcha_takes_precedence_over_login() -> None:
    html = '<input type="password"><div class="h-captcha" data-sitekey="x"></div>'
    assert detect_barrier("https://jobs.example.com", html) is Barrier.CAPTCHA_DETECTED


def test_phrases_inside_scripts_are_ignored() -> None:
    html = FORM + "<script>var help = 'Sign in to apply later';</script>"
    assert detect_barrier(GREENHOUSE, html) is None
