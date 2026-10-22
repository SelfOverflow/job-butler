# Slice 2: Job Scout & Live Link Verifier CLI

## 1. Usable Product Delivered at Slice End
At the completion of Slice 2, you will have a working job scouting CLI that fetches live postings using **Firecrawl** and direct ATS endpoints, runs deep SPA liveness checks, discards excluded employers, applies your geographic market boost, and saves active postings to SQLite:
- Run `job-butler scout run --limit 20` $\rightarrow$ Scrapes jobs matching target roles, verifies active URLs via deep ATS checks, filters out employers listed in `preferences.excluded_employers`, applies regional score boosts, and persists active jobs into SQLite.
- Run `job-butler scout list` $\rightarrow$ Prints an interactive terminal table of active jobs, displaying fit score, company, location, tier badge, and liveness status.
- Run `job-butler scout verify` $\rightarrow$ Re-verifies all stored jobs and purges/archives closed roles.

```bash
# Example usable command right after Slice 2:
job-butler scout list
# Output:
# ID       Score  Tier     Company     Title                     Location    Active  Source
# -----------------------------------------------------------------------------------------
# job_01   94     Tier 1   Stripe      Sr Full-Stack Engineer    Bengaluru   [LIVE]  Greenhouse
# job_02   92     Tier 2   Klarna      Lead Mobile Engineer      Stockholm   [LIVE]  Firecrawl
# job_03   88     Tier 3   Careem      Senior React Native Eng   Dubai, UAE  [LIVE]  Lever
```

## 2. Ingestion, Persistence & Verification Guardrails

### 2.1 SQLite Concurrency & WAL Mode (Dual-Process Protection)
To prevent `sqlite3.OperationalError: database is locked` while the background worker and FastAPI web dashboard write concurrently:
* Engine configuration enforces Write-Ahead Logging: `PRAGMA journal_mode=WAL;`.
* Busy timeout is set to 30 seconds: `connect_args={"timeout": 30.0, "check_same_thread": False}`.
* Scoped thread-safe sessions via SQLAlchemy's `async_sessionmaker` or scoped context manager.

### 2.2 Firecrawl Credit Budget & Targeted Queries
To protect your API credit allowance from unexpected exhaustion:
* Uses targeted Firecrawl `/search` queries for specific role keywords and target locations rather than broad recursive `/crawl` sweeps.
* Enforces a configurable daily credit ceiling via `MAX_DAILY_SCRAPE_CREDITS` in settings (defaults to 100 queries/day).
* Caches raw search results for 12 hours to prevent redundant re-fetching of unchanged job feeds.

### 2.3 Deep ATS Live Verification (Zero Dead Links Rule)
Before presenting or saving any job posting, the verifier performs deep inspection:
* **Ashby SPAs**: Inspects `window.__appData` payload for `"posting": null` or `"jobBoard": null` (excludes if null).
* **Workday SPAs**: Inspects configuration payload for `postingAvailable: true` (excludes if false).
* **Standard ATS (Greenhouse, Lever, SmartRecruiters, Workable)**: Verifies presence of active application form and absence of expired markers ("job no longer available", "position has been filled", "404").

### 2.2 Hard Employer Exclusions
Postings from any employer in `preferences.excluded_employers` are automatically purged (case-insensitive match on company name; list every alias, e.g. `OakNorth`, `OakNorth Bank`, `OakNorth India`). Nothing is hardcoded.

### 2.3 Multi-Dimensional Fit Rubric & Sourcing Priority
Score = `round(100 × (4·tech + 3·seniority) / 7)` + tier boost (the 40% / 30% weights rescaled to 100):
1. **Hard Requirements & Visa Gate (Pass/Fail)**: Rejects foreign roles that state "No visa sponsorship" or "Citizens/PR only". A role is domestic if it is in the first tier or names one of `work_authorization.citizen_countries`; the gate only applies when `requires_visa_for_international` is true.
2. **Tech Stack Match (≈57%)**: Share of `skills_inventory` names found in the JD, saturating at 8 matched skills.
3. **Seniority & Scope (≈43%)**: Best word overlap between the job title and a `preferences.target_roles` entry.
4. **Market Hierarchy Boost** (added on top; longest matching place name wins; loaded from `preferences.sourcing_hierarchy`; active workspace values shown):
   - **Tier 1 (India Domestic)**: +5 boost for Bengaluru / Remote India; +3 boost for Delhi NCR, Hyderabad, Pune, Mumbai.
   - **Tier 2 (EU & Nordics)**: +4 boost for Sweden, Denmark, Norway, Finland, Germany, Netherlands, etc. (EU Blue Card / Visa Sponsorship).
   - **Tier 3 (GCC / Middle East)**: +2 boost for UAE (Dubai, Abu Dhabi), Saudi Arabia, Qatar.
   - **Tier 4 (Worldwide / Global Remote)**: Standard score for UK, US, Australia, Singapore, Global Remote.

## 3. Components & Architecture
```
src/
├── storage/
│   ├── database.py          # SQLite engine & session maker (WAL mode + 30s timeout)
│   ├── models.py            # JobPosting, IngestionLog, ApplicationRecord, AuditLog ORM models
│   └── repository.py        # CRUD queries (insert_job, list_active_jobs, record_audit_event, query_audit_logs)
├── ingestion/
│   ├── base.py              # AbstractJobSource protocol and RawJobPosting DTO
│   ├── firecrawl_client.py  # Firecrawl API wrapper (scrape, search, crawl)
│   ├── sources/
│   │   ├── firecrawl_source.py # Firecrawl job search adapter
│   │   ├── greenhouse.py    # Greenhouse board API adapter
│   │   └── lever.py         # Lever board API adapter
│   ├── verifier.py          # Deep ATS live link checker (Ashby, Workday, Greenhouse, Lever)
│   ├── filter.py            # Employer exclusion filter & visa gate
│   ├── scorer.py            # Multi-dimensional rubric + market priority boost
│   └── deduplicator.py      # Title + Company + Location content hasher
└── cli_scout.py             # Subcommands: `job-butler scout run/list/verify`
```

## 4. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice2_scout.py` and `tests/integration/test_slice2_storage.py`:

1. `test_employer_exclusion_filter()`:
   - Uses a fixture profile with excluded employers (incl. aliases and case variants); asserts matching jobs are strictly excluded.
2. `test_deep_ats_verifier_ashby_closed_posting()`:
   - Mocks Ashby HTML with `window.__appData = {"posting": null}`; asserts `is_active=False`.
3. `test_deep_ats_verifier_workday_closed_posting()`:
   - Mocks Workday payload with `postingAvailable: false`; asserts `is_active=False`.
4. `test_market_hierarchy_scoring_boost()`:
   - Uses a fixture `sourcing_hierarchy`; compares an identical job description in a boosted hub vs an unboosted region; asserts correct point differential.
5. `test_firecrawl_scraper_response_parsing()`:
   - Feeds a recorded Firecrawl scrape response; asserts extraction of title, company, description, and link.
6. `test_audit_event_logging()`:
   - Records an action event with actor, status, and duration; asserts persistence in `audit_logs` table and correct JSON payload retrieval.
7. `test_cli_scout_list_command()`:
   - Seeds mock jobs into SQLite and executes `job-butler scout list` via `CliRunner`; asserts tabular display.

## 5. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice2* tests/integration/test_slice2*`
- [ ] Excluded employers are never saved to the database.
- [ ] Dead links (Ashby/Workday/404s) are rejected during verification.
- [ ] CLI commands `job-butler scout run` and `job-butler scout list` work seamlessly.
