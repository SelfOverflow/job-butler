# Slice 1: Candidate Profile & Config Core

## 1. Usable Product Delivered at Slice End
At the completion of Slice 1, you will have a working, interactive CLI tool to scaffold, manage, validate, query, and edit any candidate profile with zero friction:
- Run `job-butler profile init` $\rightarrow$ Scaffolds a new `profile/candidate_profile.yaml` from `profile/candidate_profile.template.yaml` (interactive or template mode) for any user.
- Run `job-butler profile validate` $\rightarrow$ Validates `candidate_profile.yaml` for:
  * Complete personal identity (full verbatim LinkedIn URL, email, location).
  * Unique fact-hashed `atomic_bullets` across all career positions.
  * Configured employer exclusions and target roles.
  * Structured STAR stories for behavioral Q&A.
- Run `job-butler profile update --set "preferences.min_base_salary=180000"` $\rightarrow$ Safely updates profile values via CLI, automatically creating a timestamped backup before saving.
- Run `job-butler profile add-bullet --role-id <ROLE_ID> --text "..." --skills "..."` $\rightarrow$ Interactively appends a verified atomic bullet with automatic ID generation and fact hashing.
- Run `job-butler profile backups` $\rightarrow$ Lists historical profile backups with 1-click restore capability.
- Run `job-butler profile query "Are you authorized to work in India?"` $\rightarrow$ Resolves answers against the screening bank.
- Run `job-butler profile export-master` $\rightarrow$ Compiles your canonical profile into an ATS-aligned Markdown master resume.

```bash
# Example usable command right after Slice 1:
job-butler profile init
# Output: [✓] Scaffolding candidate_profile.yaml from template... Ready to edit!
job-butler profile validate
# Output: [✓] Profile valid: Mohit Ranjan (17 atomic bullets, 4 roles, 2 STAR stories, 6 screening answers registered)
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
    ├── models.py            # Pydantic models (CandidateProfile, STARStory, AtomicBullet, etc.)
    ├── loader.py            # YAML & JSON parser with strict validation and fact hashing
    ├── updater.py           # Safe profile mutation engine with backup snapshots
    ├── screening.py         # Regex pattern matcher for ATS screening questions
    └── exporter.py          # Master resume generator
```

### Profile Models & Mutability Engine
- `ProfileLoader`:
  * Resolves environment variable placeholders (`${CANDIDATE_PHONE}`, `${CANDIDATE_CITY}`, etc.) dynamically using `.env` / system environment variables with fallback support `${VAR:-default}`.
  * Validates parsed data against `CandidateProfile` Pydantic model.
  * Provides `.snapshot()` returning a deep-copied, frozen instance for concurrency-safe background sweep execution.
- `ProfileUpdater`:
  * Validates proposed changes against Pydantic schema *before* writing to disk.
  * Creates timestamped backup in `profile/backups/candidate_profile_<timestamp>.yaml`.
  * Recalculates fact hashes for newly added or edited bullets.
  * Atomic write: writes to temporary file then renames to avoid corruption.
- `Preferences`: Target roles, excluded employers, sourcing hierarchy (India Domestic +5, EU/Nordics +4, GCC +2, Worldwide), CV page budget rules (1-page domestic vs 2-page international).
- `WorkExperience`: Company, title, normalized dates (`Mon YYYY - Mon YYYY` or `Mon YYYY - Present`), list of `AtomicBullet` items.
- `STARStory`: Situation, Task, Action, Result model for behavioral screening questions.
- `ScreeningQuestion`: Regex pattern and pre-configured typed answers.

## 3. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice1_profile.py`:

1. `test_settings_loading()`:
   - Validates reading `APP_ENV`, default SQLite path, artifact directory, and optional API keys.
2. `test_candidate_profile_valid()`:
   - Loads `candidate_profile.yaml`; asserts all fields, 4 mandatory roles, and nested bullets parse accurately.
3. `test_profile_loader_env_variable_interpolation()`:
   - Tests that `${CANDIDATE_PHONE}` and `${CANDIDATE_CITY}` are dynamically resolved from environment variables during YAML loading.
4. `test_profile_updater_creates_backup_on_mutation()`:
   - Updates candidate preferences; asserts a backup file is created in `profile/backups/` matching prior state.
4. `test_profile_updater_rejects_invalid_mutation()`:
   - Attempts to update with invalid email or missing mandatory fields; asserts `ValidationError` is raised and profile file remains untouched.
5. `test_candidate_profile_duplicate_bullet_ids_rejected()`:
   - Injects a duplicate bullet ID; asserts `ValidationError` is raised.
6. `test_star_stories_schema_validation()`:
   - Verifies STAR story models require situation, task, action, and result fields.
7. `test_screening_question_resolver()`:
   - Tests pattern matching against common ATS screening prompts (India work authorization, international sponsorship, notice period).
8. `test_cli_profile_validate_and_update_commands()`:
   - Executes `job-butler profile validate` and `job-butler profile update` via Click's `CliRunner`; asserts exit code `0`.

## 4. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice1*`
- [ ] Strict type checking passes with `mypy --strict src/profile src/config`
- [ ] Linter clean with `ruff check`
- [ ] Profile is safely mutable with automated backups.
