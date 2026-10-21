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
├── Dockerfile               # Multi-stage image (Next.js standalone + Python 3.11 + Playwright + Typst)
├── docker-compose.yml       # Local 24/7 dual-service runner (frontend:3000, backend:8000)
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

## 2. Immutable Candidate Profile & Domain Rules

When writing code, tailoring resumes, or scraping jobs, you must observe these strict candidate rules:

### 2.1 Candidate Identity
- **Name**: Mohit Ranjan
- **Location**: Injected via `.env` (`${CANDIDATE_CITY}`, `${CANDIDATE_STATE}`, India)
- **Phone**: Injected via `.env` (`${CANDIDATE_PHONE}`)
- **Email**: `mohit.ranjan.910@gmail.com`
- **LinkedIn Directive**: Always display the full verbatim LinkedIn URL on all CVs, cover letters, and applications: `https://www.linkedin.com/in/mohit-ranjan-759188169` (never trim or shorten).
- **GitHub**: `https://github.com/MohitR1999`

### 2.2 Mandatory 4 Roles (Never Omit)
Every generated resume MUST explicitly include all 4 full-time and internship positions:
1. **OakNorth India** — Technical Lead (Individual Contributor) (Jul 2025 - Present)
2. **Tejas Networks Ltd** — Senior Engineer (Apr 2024 - Jul 2025)
3. **Tejas Networks Ltd** — Research & Development Engineer (Jul 2021 - Apr 2024)
4. **Stepswatch SASU** — Frontend Developer Intern (Mar 2020 - May 2020)

### 2.3 Excluded Employers (Hard Auto-Purge)
Never search for, scrape, recommend, or apply to postings from:
- **OakNorth** (`oaknorth.com`, `oaknorth.co.uk`, OakNorth Bank, OakNorth India)
- **Tejas Networks** (`tejasnetworks.com`, Tejas Networks Ltd)
- **Stepswatch** (Stepswatch SASU)

### 2.4 Sourcing Scope & Regional Boost Hierarchy
- **Tier 1 (India Domestic)**: Resident, zero visa friction.
  - +5 point boost: Bengaluru / Bangalore, Remote India.
  - +3 point boost: Delhi NCR, Gurugram, Noida, Hyderabad, Pune, Mumbai, Chennai.
- **Tier 2 (EU & Nordics)**: Top-tier international priority (Visa Sponsorship / EU Blue Card, +4 point boost).
  - Sweden, Denmark, Norway, Finland, Germany, Netherlands, Ireland, France, Spain, Switzerland, etc.
- **Tier 3 (GCC / Middle East)**: High-priority international (Visa Sponsorship / Relocation, +2 point boost).
  - UAE (Dubai, Abu Dhabi), Saudi Arabia, Qatar, Kuwait, Bahrain, Oman.
- **Tier 4 (Worldwide Relocation & Global Remote)**: Base score.
  - UK, US, Canada, Australia, Singapore, Japan, Worldwide Remote.

### 2.5 Zero Hallucination & ATS Standards
- **Zero Hallucination Constraint**: Resumes are generated **strictly by selecting, ranking, and highlighting verified atomic bullet IDs** from `profile/candidate_profile.yaml`. The agent is strictly forbidden from fabricating metrics, projects, or employment history.
- **Geographic Page Budget Rule**:
  - India Domestic: Exactly **1 page**.
  - International Relocation: Exactly **2 pages**.
  - Cover Letter: Exactly **1 page** (compile to both PDF and clean line-broken `.txt`).
- **Standard ATS Headings**: Canonical headers only (`Professional Experience`, `Technical Skills`, `Education`, `Projects`, `Certifications`).
- **Date Normalization**: Strictly `Mon YYYY - Mon YYYY` (or `Mon YYYY - Present`) using a single ASCII hyphen `-`.
- **Text Layer Extraction Verification**: Every compiled PDF must be verified via `pypdf`/`pdftotext` to confirm 100% extractable text and presence of 25–35 exact JD keywords.

---

## 3. Engineering & SDLC Guidelines (Strict TDD)

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

## 4. Candidate Profile Mutability Protocol
- The candidate profile at `profile/candidate_profile.yaml` can be edited at any time directly, via CLI (`job-butler profile update`), or through the Web UI (`PUT /api/profile`).
- Before any programmatic save, the system **MUST** create a timestamped backup in `profile/backups/candidate_profile_<YYYYMMDD_HHMMSS>.yaml`.
- The 24/7 background scheduler dynamically re-reads `candidate_profile.yaml` on every sweep cycle (hot-reloading).

