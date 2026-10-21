# Slice 2: Deterministic Ingestion & Link Verification Engine

## 1. Goal & Scope
Build a high-performance job scraping, verification, and persistence pipeline. It leverages the **Firecrawl API** to seamlessly bypass anti-bot protections, render JavaScript pages, and crawl target job boards and career search engines into clean markdown and structured postings. Additionally supports direct ATS feeds (Greenhouse, Lever), verifies that listings are live and active via HTTP probes, deduplicates entries, and persists records into SQLite.

## 2. Components & Architecture
```
src/
├── storage/
│   ├── __init__.py
│   ├── database.py          # SQLAlchemy engine, session maker, DB initialization
│   ├── models.py            # JobPosting, IngestionLog, ApplicationRecord ORM models
│   └── repository.py        # CRUD operations for jobs and status tracking
└── ingestion/
    ├── __init__.py
    ├── base.py              # AbstractJobSource protocol and RawJobPosting DTO
    ├── firecrawl_client.py  # Wrapper client for Firecrawl API (scrape, crawl, map)
    ├── sources/
    │   ├── firecrawl_source.py # Firecrawl-based web scraping adapter for job boards
    │   ├── greenhouse.py    # Greenhouse board API adapter
    │   └── lever.py         # Lever board API adapter
    ├── verifier.py          # HTTP link liveness and 'expired posting' DOM checker
    └── deduplicator.py      # Content hashing (normalized title + company + location)
```

## 3. TDD Test Specification (Red Phase)
Before implementation, the following unit and integration tests will be written in `tests/unit/` and `tests/integration/`:

1. `test_raw_job_posting_normalization()`:
   - Asserts cleaning of HTML entities, whitespace normalization, and ISO timestamp parsing.
2. `test_firecrawl_scraper_adapter()`:
   - Uses a recorded mock response from Firecrawl `/scrape` and `/map` endpoints.
   - Asserts extraction of markdown JD, job title, company name, location, and metadata.
3. `test_greenhouse_source_adapter()`:
   - Uses a recorded JSON fixture of a Greenhouse jobs endpoint.
   - Asserts correct extraction of title, company, location, URL, and raw markdown/text description.
3. `test_lever_source_adapter()`:
   - Uses a recorded JSON fixture of a Lever jobs endpoint.
   - Asserts extraction of categories (team, commitment, location) and application URL.
4. `test_link_verifier_live_url()`:
   - Mocks HTTP 200 OK with valid job content; asserts `is_active=True`.
5. `test_link_verifier_expired_url()`:
   - Mocks HTTP 404, 410, and HTTP 200 with "This job has been filled / expired" text; asserts `is_active=False`.
6. `test_deduplication_and_repository_upsert()`:
   - Verifies duplicate postings across multiple runs update `last_verified_at` without duplicating database rows.

## 4. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_ingestion* tests/unit/test_storage*`
- [ ] Hermetic tests using `respx` / mock HTTP clients (no real external network calls during unit tests)
- [ ] Strict type checking passes with `mypy --strict src/ingestion src/storage`
- [ ] Clean SQLite migration and persistence verified.

