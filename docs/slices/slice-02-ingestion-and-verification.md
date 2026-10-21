# Slice 2: Job Scout & Live Link Verifier CLI

## 1. Usable Product Delivered at Slice End
At the completion of Slice 2, you will have a working job scouting CLI that fetches live postings using **Firecrawl** and ATS endpoints, verifies their links are active, deduplicates records, and saves them to SQLite:
- Run `job-butler scout run --limit 10` $\rightarrow$ Scrapes jobs matching your target roles, tests every URL with live HTTP status probes, and persists active jobs into SQLite.
- Run `job-butler scout list` $\rightarrow$ Prints an interactive terminal table of all active discovered jobs, their companies, locations, source, and liveness status.
- Run `job-butler scout verify` $\rightarrow$ Re-checks existing jobs in the database and archives expired listings.

```bash
# Example usable command right after Slice 2:
job-butler scout list
# Output:
# ID       Company     Title                     Location    Active  Source
# -------------------------------------------------------------------------
# job_01   Stripe      Sr Backend Engineer       Remote      [LIVE]  Greenhouse
# job_02   Anthropic   Distributed Systems Eng   SF, CA      [LIVE]  Lever
# job_03   OpenAI      AI Platform Engineer      Remote      [LIVE]  Firecrawl
```

## 2. Components & Architecture
```
src/
├── storage/
│   ├── database.py          # SQLite engine & session maker
│   ├── models.py            # JobPosting, IngestionLog, ApplicationRecord ORM models
│   └── repository.py        # CRUD queries (insert_job, list_active_jobs, archive_expired)
├── ingestion/
│   ├── base.py              # AbstractJobSource protocol and RawJobPosting DTO
│   ├── firecrawl_client.py  # Firecrawl API wrapper (scrape, search, map)
│   ├── sources/
│   │   ├── firecrawl_source.py # Firecrawl job search adapter
│   │   ├── greenhouse.py    # Greenhouse board API adapter
│   │   └── lever.py         # Lever board API adapter
│   ├── verifier.py          # HTTP link liveness and expired DOM text probe
│   └── deduplicator.py      # Title + Company + Location content hasher
└── cli_scout.py             # Subcommands: `job-butler scout run/list/verify`
```

## 3. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice2_scout.py` and `tests/integration/test_slice2_storage.py`:

1. `test_firecrawl_scraper_response_parsing()`:
   - Feeds a recorded Firecrawl scrape response; asserts extraction of job title, company, description, and link.
2. `test_greenhouse_and_lever_parsers()`:
   - Validates ATS board endpoints without making live web calls.
3. `test_link_verifier_live_vs_expired()`:
   - Mocks HTTP 200 (live) vs 404 / 410 (expired) vs 200 with "job no longer available" text.
4. `test_job_repository_deduplication()`:
   - Asserts inserting the same job twice updates `last_verified_at` without creating duplicate records.
5. `test_cli_scout_list_command()`:
   - Seeds mock jobs into SQLite and executes `job-butler scout list` via `CliRunner`; asserts tabular display.

## 4. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice2* tests/integration/test_slice2*`
- [ ] All network calls mocked with `respx` for deterministic, fast unit tests.
- [ ] SQLite database initialized automatically in `./data/job_butler.db`.
- [ ] CLI commands `job-butler scout run` and `job-butler scout list` work out of the box.
