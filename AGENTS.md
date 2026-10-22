# AGENTS.md: Autonomous Coding Agent Guide for Job Butler

Welcome, Agent. This repository is **Job Butler**, a self-contained, 24/7 autonomous job discovery, resume tailoring, and application platform built for **Mohit Ranjan**.

Every agent operating in this codebase must strictly adhere to the guidelines, domain constraints, and workflow patterns detailed in this document.

---

## 1. Monorepo Structure & Navigation Map

```
job_butler/
├── AGENTS.md                # [YOU ARE HERE] Canonical instructions & context for all AI agents
├── README.md                # Project overview and quickstart guide
├── Makefile                 # Standardized task runner: make test, make lint, make dev, make up
├── pyproject.toml           # Python dependencies, tools (ruff, mypy, pytest)
├── Dockerfile               # Multi-stage image (Next.js static export + Python 3.11 + Playwright + Typst)
├── docker-compose.yml       # Local 24/7 single-container runner (UI + API + worker on :8000)
├── .github/
│   └── workflows/           # GitHub Actions CI/CD (ci.yml, deploy.yml)
├── docs/
│   ├── architecture.md      # Full system architecture, dual-runtime model, and design rules
│   └── slices/              # 7 incremental, test-driven deliverable slice specifications
│       ├── slice-01-profile-and-config.md
│       ├── slice-02-ingestion-and-verification.md
│       ├── slice-03-tailor-agent.md
│       ├── slice-04-realtime-web-dashboard.md
│       ├── slice-05-auto-apply-and-hitl.md
│       ├── slice-06-autopilot-and-upskilling.md
│       └── slice-07-docker-ec2-terraform-cicd.md
├── profile/
│   ├── candidate_profile.yaml # Single source of truth for candidate career data & preferences
│   └── backups/             # Automated timestamped snapshots created before every mutation
├── templates/
│   ├── resume_domestic.typ  # 1-page single-column Typst ATS template for India domestic roles
│   ├── resume_international.typ # 2-page single-column Typst ATS template for international roles
│   └── cover_letter.typ     # 1-page Typst cover letter template
├── terraform/               # Cost-effective AWS EC2 (t4g.small/t3.micro), EBS, SSM modules
├── frontend/                # Next.js 14 App Router + React.js + Tailwind CSS UI Dashboard
│   ├── app/                 # Routes: / (Dashboard), /jobs, /profile (Editor), /hitl (Interventions)
│   ├── components/          # Reusable UI widgets (JobCard, LiveFeed, ProfileForm, YamlEditor)
│   └── lib/                 # Type-safe API client and auto-reconnecting WebSocket client
├── src/                     # Python core backend, agents, scheduler, and CLI
│   ├── cli.py               # Unified CLI entrypoint (`job-butler`)
│   ├── config/              # Typed Pydantic Settings
│   ├── profile/             # Profile loader, models, safe updater, screening matcher
│   ├── ingestion/           # Firecrawl client, ATS adapters, deep live-link verifier, deduplicator
│   ├── storage/             # SQLite / SQLAlchemy models, database session, repository
│   ├── agents/
│   │   ├── tailor/          # Resume tailoring engine (Drafter-Reviewer loop, Typst, PDF verifier)
│   │   └── navigator/       # Playwright browser automation, DOM inspector, barrier detector
│   ├── scheduler/           # 24/7 background autopilot orchestrator with profile hot-reloading
│   ├── analytics/           # Market trend aggregator and mathematical upskilling ROI engine
│   └── server/              # FastAPI REST API, WebSocket broadcaster, and static handlers
└── tests/                   # Strict TDD test suites mirroring src/ with recorded hermetic fixtures
    ├── unit/
    ├── integration/
    └── fixtures/
```

---

## 2. Universal Data-Driven Design & Candidate Independence

### 2.1 Critical Rule: Zero Hardcoding of Candidate Data
While this repository is currently initialized with career data for **Mohit Ranjan**, **ALL Python backend logic, ATS scoring algorithms, Typst resume templates, and scraping filters MUST be 100% generic and data-driven**:
- **Never hardcode names, phone numbers, emails, LinkedIn URLs, employers, or locations in source code**.
- All personal identity, career history, excluded employers, target roles, and market tiers MUST be parsed dynamically from `profile/candidate_profile.yaml` (and environment variables).
- Any developer or job seeker must be able to fork/clone this repository, provide their own `candidate_profile.yaml` and `.env`, and run the entire platform with zero friction.

### 2.2 Active Candidate Workspace Context (Mohit Ranjan)
When evaluating the active configuration in this repository, the agent operates with these parameters loaded from `profile/candidate_profile.yaml`:
- **Identity**: Mohit Ranjan, Delhi, India (Location & Phone masked via `.env`).
- **LinkedIn Directive**: Full verbatim LinkedIn URL rendered on all generated documents.
- **Active Excluded Employers**: OakNorth, Tejas Networks, Stepswatch (loaded from `preferences.excluded_employers`).
- **Active Target Roles**: Senior Full-Stack Engineer, Technical Lead, Lead Mobile Engineer, Senior React Native Engineer, Distributed Systems Engineer.
- **Active Market Tiers** (loaded from `preferences.sourcing_hierarchy`): Tier 1 (India Domestic +5/+3), Tier 2 (EU & Nordics +4), Tier 3 (GCC +2), Tier 4 (Worldwide).

---

## 3. Zero-Friction Setup for New Candidates (`job-butler profile init`)
Any new user can adopt Job Butler in 3 steps:
1. `cp .env.example .env` (configure API keys & masked contact info).
2. `cp profile/candidate_profile.template.yaml profile/candidate_profile.yaml` (or run `job-butler profile init`).
3. Run `job-butler profile validate` or `make up`.

---

## 4. Engineering & SDLC Guidelines (Strict TDD)

Any code modification in this repo must follow standard **Test-Driven Development (TDD)**:
1. **Red**: Write a failing unit or integration test defining the behavior.
2. **Green**: Write the minimal viable code to pass the test.
3. **Refactor**: Clean up implementation, enforce strict typing (`mypy --strict`), and run linter (`ruff`).
4. **Hermetic Testing**: Never make real external network or LLM API calls in automated test suites. Use `respx` for HTTP mocking and mock LLM providers.

### Standard Commands (`Makefile`)
```bash
make test         # Run all backend pytest and frontend npm test suites
make lint         # Run ruff check and mypy --strict
make dev          # Run FastAPI backend and Next.js frontend in development mode
make up           # Start full containerized stack locally via Docker Compose
make down         # Stop local Docker Compose containers
```

---

## 5. Candidate Profile Mutability Protocol
- The candidate profile at `profile/candidate_profile.yaml` can be edited at any time directly, via CLI (`job-butler profile update`), or through the Web UI (`PUT /api/profile`).
- Before any programmatic save, the system **MUST** create a timestamped backup in `profile/backups/candidate_profile_<YYYYMMDD_HHMMSS>.yaml`.
- The 24/7 background scheduler dynamically re-reads `candidate_profile.yaml` on every sweep cycle (hot-reloading).

