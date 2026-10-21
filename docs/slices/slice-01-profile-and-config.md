# Slice 1: Candidate Profile & Config Core

## 1. Goal & Scope
Deliver a strictly typed, validated, and machine-readable Candidate Knowledge Base and configuration engine. This forms the single source of truth for the entire application, guaranteeing zero hallucinations during resume generation and providing instant answers for automated job applications.

## 2. Components & Architecture
```
src/
├── config/
│   ├── __init__.py
│   └── settings.py          # App settings (Pydantic Settings: APP_ENV, DB_URL, API keys)
└── profile/
    ├── __init__.py
    ├── models.py            # Pydantic domain models (CandidateProfile, Experience, Bullet, Skill, etc.)
    ├── loader.py            # YAML & JSON profile parser with strict validation
    └── screening.py         # Screening question matcher (Regex & semantic answer resolver)
```

### Key Models
- `PersonalInfo`: Contact, links, work authorization (visas, citizenship).
- `Preferences`: Target roles, target locations, remote policy, minimum salary floor, excluded companies.
- `SkillInventory`: Languages, frameworks, cloud/devops, databases, with proficiency and years.
- `AtomicBullet`: Unique ID, immutable text, skill tags, quantitative metrics, domain tags.
- `WorkExperience`: Company, title, dates, list of `AtomicBullet` items.
- `Project`: Name, repo URL, live URL, list of `AtomicBullet` items.
- `Education` & `Certification`: Degree, school, cert details.
- `ScreeningQuestion`: Regex pattern, answer type (`boolean`, `number`, `text`), pre-configured answer.

## 3. TDD Test Specification (Red Phase)
Before any production code is written, the following tests will be constructed in `tests/unit/`:

1. `test_settings_loading()`:
   - Verifies loading from environment variables and `.env`.
   - Defaults `APP_ENV` to `"local"`.
   - Validates paths for SQLite database and artifacts.
   - Validates optional API keys (`FIRECRAWL_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`).
2. `test_candidate_profile_valid_schema()`:
   - Validates a complete `candidate_profile.yaml` fixture against `CandidateProfile`.
   - Asserts all bullet IDs are unique across experience and projects.
3. `test_candidate_profile_missing_required_fields()`:
   - Ensures `ValidationError` is raised when required contact info or salary floor is missing.
4. `test_atomic_bullet_immutability_and_hashing()`:
   - Verifies each bullet point generates a deterministic hash to prevent runtime tampering.
5. `test_screening_question_resolver()`:
   - Evaluates regex matching against variations of standard ATS screening prompts:
     * `"How many years of Python experience do you have?"` $\rightarrow$ `6`
     * `"Are you legally authorized to work in the US?"` $\rightarrow$ `True`
     * `"Will you now or in the future require visa sponsorship?"` $\rightarrow$ `False`
     * `"What is your desired salary?"` $\rightarrow$ `175000`

## 4. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_profile*`
- [ ] Strict type checking passes with `mypy --strict src/profile src/config`
- [ ] Linter clean with `ruff check`
- [ ] Example `profile/candidate_profile.example.yaml` is provided and passes validation.

