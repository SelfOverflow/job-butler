# Job Butler 🤵‍♂️

> Autonomous 24/7 Career Discovery, Tailoring, and Application Platform

Job Butler is a self-contained monorepo that continuously discovers matching job openings across global tech hubs, verifies active links, crafts tailored ATS-optimized resumes using verified career facts, and navigates online job applications with minimal human intervention.

Every CLI command has full parity with the **Web Command Center** dashboard on `http://localhost:8000`.

---

## Key Features

- **24/7 Autopilot Scheduler**: Continuously monitors target job boards via the **Firecrawl API** and direct ATS endpoints (Greenhouse, Lever, Ashby, Workday).
- **Zero-Hallucination Resume Tailoring**: Dynamically selects, ranks, and emphasizes verified atomic bullet points from your master profile to maximize ATS scores without inventing claims.
- **Geographic Page Budgeting**: Automatically compiles strictly 1-page resumes for domestic (Tier 1) roles and 2-page resumes for international relocation roles using **Typst**.
- **Deep Live Verification**: Deep DOM and payload probes (Ashby SPAs, Workday SPAs) guarantee zero dead links or expired postings.
- **Web Command Center**: Built with **Next.js 16**, **React**, and **Tailwind CSS**, served by FastAPI as a static export on a single port (`8000`), featuring live WebSocket telemetry, stage progress bars, cancel buttons, and run history.
- **Human-in-the-Loop (HITL) Safety**: Applications are **never** auto-submitted without explicit human confirmation. Escalates portals requiring manual account creation, CAPTCHAs, or MFA with copy-ready answers.
- **Market Trends & Upskilling ROI**: Aggregates in-demand tech stacks and mathematically ranks missing skills by the number of active job openings they would unlock.
- **1-Command Local Execution**: Runs locally for **$0** via Docker Compose (`make up`) or native Python virtualenv (`make dev`).

---

## Monorepo Layout

```text
job_butler/
├── AGENTS.md                # Autonomous AI agent instructions & domain rules
├── docs/                    # Architecture blueprints & 8 deliverable slice specs
├── profile/                 # Candidate master profile (YAML) & automated backups
├── templates/               # Typst ATS resume and cover letter templates
├── frontend/                # Next.js 16 + React + Tailwind CSS dashboard
├── src/                     # Python core backend, agents, scrapers, and CLI
├── tests/                   # Strict TDD test suites (backend & frontend)
├── terraform/               # Cost-effective AWS EC2 infrastructure modules
├── Makefile                 # Developer and agent task runner
├── Dockerfile               # Multi-stage production container
└── docker-compose.yml       # Local single-container runner (port 8000)
```

---

## Quickstart: Running Locally

### Step 1: Environment & Profile Setup

Job Butler is 100% data-driven with **zero hardcoding** of personal career data:

```bash
# 1. Copy environment template and add your API keys (Gemini, Firecrawl, etc.)
cp .env.example .env

# 2. Initialize your candidate profile from template
cp profile/candidate_profile.template.yaml profile/candidate_profile.yaml
# (Or use the CLI: job-butler profile init)
```

---

### Step 2: Choose Your Local Run Mode

#### Option A: Docker Compose (Recommended — Zero Host Dependencies)

Requires only [Docker](https://docs.docker.com/get-docker/):

```bash
# Build and start container in the background (UI + API + Worker on port 8000)
make up

# View real-time logs
docker compose logs -f

# Stop the stack
make down
```

Open **`http://localhost:8000`** in your browser. All data (`./data`) and generated resumes (`./artifacts`) persist locally on your host.

---

#### Option B: Native Development Mode (Python + Node.js)

Requires **Python 3.11+** and **Node.js 20+**:

```bash
# 1. Set up Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
playwright install chromium

# 2. Install frontend dependencies
cd frontend && npm install && cd ..

# 3. Run both backend (:8000) and frontend dev server (:3000) concurrently:
make dev
```

- **Frontend UI (Hot Reloading)**: `http://localhost:3000` (automatically proxies `/api` and `/ws` to `:8000`)
- **Backend API & Swagger Docs**: `http://localhost:8000/docs`

To run them individually in separate terminals:
```bash
make dev-backend   # FastAPI server with reload on :8000
make dev-frontend  # Next.js dev server on :3000
```

---

## Operating Job Butler

### From the Web Dashboard (`http://localhost:8000`)

- **Command Center (`/run`)**: Launch Scout sweeps, trigger link re-verifications, or tailor all matches with real-time stage progress bars and cancel controls.
- **Jobs Board (`/jobs`)**: Filter and sort matching jobs, with 1-click *Tailor*, *Re-verify*, and *Prepare application* contextual buttons.
- **HITL Review Queue (`/hitl`)**: Review filled form plans and screenshots, answer unanswerable portal questions, and approve submissions.
- **Profile Editor (`/profile`)**: Update preferences, edit raw YAML, test screening question answers, append experience bullets, and export your master resume.
- **Run History (`/runs`)**: View all past runs, duration, parameter snapshots, and result/error logs.
- **Audit Feed (`/audit`)**: Inspect every action taken by the agent and human.
- **Settings (`/settings`)**: Check integration status (Gemini, Firecrawl, Anthropic, OpenAI) without exposing secret keys.

### From the Unified CLI (`job-butler`)

```bash
# Profile commands
job-butler profile validate
job-butler profile query "Are you authorized to work in the United States?"
job-butler profile export-master --output master.md

# Scout job discovery & verification
job-butler scout run --limit 20
job-butler scout verify
job-butler scout list --min-score 75

# Resume tailoring
job-butler tailor --job-id <JOB_ID>
job-butler tailor --all-matches --min-score 80

# Auto-apply (prepare application for review)
job-butler apply --job-id <JOB_ID>
job-butler apply approve <JOB_ID>

# Autopilot background scheduler
job-butler autopilot start --interval-hours 1
job-butler autopilot status

# Upskilling ROI analysis
job-butler analytics report
```

---

## Testing & Quality Assurance

Job Butler enforces strict **Test-Driven Development (TDD)** and typing:

```bash
# Run all backend pytest and frontend vitest test suites
make test

# Run static analysis and linting (ruff + mypy --strict)
make lint

# Auto-format codebase
make format

# Build production static export of the frontend
cd frontend && npm run build
```

---

## Architecture & Documentation

- [Full Architecture Blueprint](docs/architecture.md)
- [Autonomous Agent Guide & Constraints](AGENTS.md)
- [Deliverable Slice Specifications](docs/slices/)
