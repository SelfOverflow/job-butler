from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "00000",
}


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> "Run":
    monkeypatch.chdir(tmp_path)  # Never pick up the developer's real .env or profile.
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.yaml"))
    return Run(tmp_path / "profile.yaml")


class Run:
    def __init__(self, profile: Path) -> None:
        self.profile = profile

    def __call__(self, *args: str, exit_code: int = 0) -> str:
        result = CliRunner().invoke(app, list(args))
        assert result.exit_code == exit_code, result.output
        return result.output

    def init(self) -> None:
        self("profile", "init", "--template", str(TEMPLATE))


def test_init_scaffolds_profile_from_template(run: Run) -> None:
    out = run("profile", "init", "--template", str(TEMPLATE))
    assert "Ready to edit" in out
    assert run.profile.read_text(encoding="utf-8") == TEMPLATE.read_text(encoding="utf-8")


def test_init_refuses_to_overwrite_without_force(run: Run) -> None:
    run.profile.write_text("mine", encoding="utf-8")
    out = run("profile", "init", "--template", str(TEMPLATE), exit_code=1)
    assert "already exists" in out
    assert run.profile.read_text(encoding="utf-8") == "mine"
    run("profile", "init", "--template", str(TEMPLATE), "--force")
    assert run.profile.read_text(encoding="utf-8") != "mine"


def test_validate_prints_summary(run: Run) -> None:
    run.init()
    out = run("profile", "validate")
    assert out.strip() == (
        "[✓] Profile valid: Jane Doe "
        "(3 atomic bullets, 2 roles, 1 STAR stories, 5 screening answers registered)"
    )


def test_validate_reports_schema_errors_with_field_paths(run: Run) -> None:
    run.init()
    text = run.profile.read_text(encoding="utf-8").replace('"Senior Backend Engineer"', '""')
    run.profile.write_text(text, encoding="utf-8")
    out = run("profile", "validate", exit_code=1)
    assert "[✗] Profile invalid" in out
    assert "work_experience.0.title" in out


def test_validate_reports_missing_env_and_file(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    assert "Profile not found" in run("profile", "validate", exit_code=1)
    run.init()
    monkeypatch.delenv("CANDIDATE_PHONE")
    assert "CANDIDATE_PHONE" in run("profile", "validate", exit_code=1)


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Are you authorized to work in the US?", "Yes"),
        ("Do you require sponsorship?", "No"),
        ("What is your notice period?", "2 weeks"),
        ("Years of experience with Python?", "6"),
    ],
)
def test_query_resolves_screening_answers(run: Run, question: str, answer: str) -> None:
    run.init()
    assert run("profile", "query", question).strip() == answer


def test_query_without_match_exits_nonzero(run: Run) -> None:
    run.init()
    assert "No matching screening answer" in run(
        "profile", "query", "Favourite colour?", exit_code=1
    )
