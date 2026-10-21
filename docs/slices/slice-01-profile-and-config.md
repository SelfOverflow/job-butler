# Slice 1: Candidate Profile & Config Core

## 1. Usable Product Delivered at Slice End
At the completion of Slice 1, you will have a working, interactive CLI tool to manage and test your career profile:
- Run `job-butler profile validate` $\rightarrow$ Validates `candidate_profile.yaml` for complete contact info, preferences, and guarantees all atomic bullet IDs are unique and untampered.
- Run `job-butler profile query "Are you authorized to work in the US?"` $\rightarrow$ Tests the automated screening question resolver in real time.
- Run `job-butler profile export-master` $\rightarrow$ Compiles your raw profile into a clean, canonical Markdown master resume.

```bash
# Example usable command right after Slice 1:
job-butler profile validate --profile profile/candidate_profile.yaml
# Output: [✓] Profile valid: Alex Doe (12 atomic bullets, 18 skills, 6 screening answers registered)
```

## 2. Components & Architecture
```
src/
├── cli.py                   # Click/Typer CLI entrypoint (`job-butler`)
├── config/
│   ├── __init__.py
│   └── settings.py          # App settings (Pydantic Settings: APP_ENV, FIRECRAWL_API_KEY, etc.)
└── profile/
    ├── __init__.py
    ├── models.py            # Pydantic models (CandidateProfile, WorkExperience, AtomicBullet, etc.)
    ├── loader.py            # YAML & JSON parser with strict validation and fact hashing
    ├── screening.py         # Regex pattern matcher for ATS screening questions
    └── exporter.py          # Master resume generator
```

## 3. TDD Red-Phase Test Specification
The following tests in `tests/unit/test_slice1_profile.py` define the criteria before writing code:

1. `test_settings_loading()`:
   - Validates reading `APP_ENV`, default SQLite path, artifact directory, and optional API keys.
2. `test_candidate_profile_valid()`:
   - Loads a valid `candidate_profile.yaml` fixture; asserts all fields and nested bullets parse accurately.
3. `test_candidate_profile_duplicate_bullet_ids_rejected()`:
   - Injects a duplicate bullet ID; asserts `ValidationError` is raised.
4. `test_screening_question_resolver()`:
   - Tests pattern matching against common ATS screening prompts:
     * `"How many years of Python experience do you have?"` $\rightarrow$ `6`
     * `"Are you legally authorized to work in the US?"` $\rightarrow$ `True`
     * `"Will you now or in the future require visa sponsorship?"` $\rightarrow$ `False`
5. `test_cli_profile_validate_command()`:
   - Executes `job-butler profile validate` via Click's `CliRunner`; asserts exit code `0` and success output.

## 4. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice1*`
- [ ] Strict type checking passes with `mypy --strict src/profile src/config`
- [ ] Linter clean with `ruff check`
- [ ] `job-butler profile validate` and `job-butler profile query` run successfully in your terminal.
