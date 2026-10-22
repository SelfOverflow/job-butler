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


def test_update_sets_values_and_backs_up(run: Run) -> None:
    run.init()
    out = run("profile", "update", "--set", "work_experience.0.title=Staff Engineer")
    assert "[✓] Updated work_experience.0.title" in out
    assert "Staff Engineer" in run.profile.read_text(encoding="utf-8")
    assert "profile_" in run("profile", "backups")


def test_update_applies_all_sets_atomically(run: Run) -> None:
    run.init()
    before = run.profile.read_text(encoding="utf-8")
    out = run(
        "profile", "update",
        "--set", "preferences.min_base_salary=200000",
        "--set", "personal_info.email=not-an-email",
        exit_code=1,
    )  # fmt: skip
    assert "personal_info.email" in out
    assert run.profile.read_text(encoding="utf-8") == before
    assert "No backups yet" in run("profile", "backups")


def test_update_order_independent_within_one_call(run: Run) -> None:
    run.init()
    run(
        "profile", "update",
        "--set", "preferences.min_base_salary=3500000",
        "--set", "preferences.currency=INR",
    )  # fmt: skip
    assert "INR" in run.profile.read_text(encoding="utf-8")


@pytest.mark.parametrize("assignment", ["no-equals-sign", "=value"])
def test_update_rejects_malformed_set(run: Run, assignment: str) -> None:
    run.init()
    assert "Expected PATH=VALUE" in run("profile", "update", "--set", assignment, exit_code=1)


def test_add_bullet(run: Run) -> None:
    run.init()
    out = run(
        "profile", "add-bullet",
        "--role-id", "exp_company_beta",
        "--text", "Cut CI time by 40% with remote caching.",
        "--skills", "Bazel, GitHub Actions",
    )  # fmt: skip
    assert out.startswith("[✓] Added bullet b_")
    assert "4 atomic bullets" in run("profile", "validate")
    assert "Unknown role" in run(
        "profile", "add-bullet", "--role-id", "nope", "--text", "x", exit_code=1
    )


def test_backups_and_restore(run: Run) -> None:
    run.init()
    original = run.profile.read_text(encoding="utf-8")
    run("profile", "update", "--set", "work_experience.0.title=Changed")
    backup_name = run("profile", "backups").split()[-1]

    assert "[✓] Restored" in run("profile", "restore", backup_name)
    assert run.profile.read_text(encoding="utf-8") == original
    assert "No such backup" in run("profile", "restore", "missing.yaml", exit_code=1)
