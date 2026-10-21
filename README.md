# Job Butler 🤵‍♂️

> Autonomous 24/7 Career Discovery, Tailoring, and Application Platform

Job Butler is a self-contained monorepo that continuously discovers matching job openings across global tech hubs, verifies active links, crafts tailored ATS-optimized resumes using verified career facts, and navigates online job applications with minimal human intervention.

---

## Key Features

- **24/7 Autopilot Scheduler**: Continuously monitors target job boards via the **Firecrawl API** and direct ATS endpoints (Greenhouse, Lever, etc.).
- **Zero-Hallucination Resume Tailoring**: Dynamically selects, ranks, and emphasizes verified atomic bullet points from your master profile to maximize ATS scores without inventing claims.
- **Geographic Page Budgeting**: Automatically compiles strictly 1-page resumes for India Domestic roles and 2-page resumes for International Relocation roles using **Typst**.
- **Deep Live Verification**: Deep DOM and payload probes (Ashby SPAs, Workday SPAs) guarantee zero dead links or expired postings.
- **Real-Time Web Dashboard**: Built with **Next.js 14**, **React.js**, and **Tailwind CSS**, featuring live WebSocket telemetry, ATS match badges, 1-click PDF resume downloads, and an interactive Profile Editor.
- **Human-in-the-Loop (HITL) Queue**: Automatically escalates portals requiring manual account creation, CAPTCHAs, or MFA directly to your web dashboard with copy-ready answers.
- **Market Trends & Upskilling ROI**: Aggregates in-demand tech stacks and mathematically ranks missing skills by the number of active job openings they would unlock.
- **Dual Runtime & Cost Optimization**: Runs locally for **$0** via `docker compose`, or deployable to a low-cost AWS EC2 instance (`t4g.small` / `t3.micro`, ~$3–$8/mo) via **Terraform** and **GitHub Actions**.

---

## Monorepo Layout

```
job_butler/
├── AGENTS.md                # Autonomous AI agent instructions & domain rules
├── docs/                    # Architecture blueprints & 7 deliverable slice specs
├── profile/                 # Candidate master profile (YAML) & automated backups
├── templates/               # Typst ATS resume and cover letter templates
├── frontend/                # Next.js 14 + React + Tailwind CSS dashboard
├── src/                     # Python core backend, agents, scrapers, and CLI
├── tests/                   # Strict TDD test suites (backend & frontend)
├── terraform/               # Cost-effective AWS EC2 infrastructure modules
├── Makefile                 # Developer and agent task runner
├── Dockerfile               # Multi-stage production container
└── docker-compose.yml       # 1-click local dual-container orchestration
```

---

## Quickstart

### Local Execution (Docker Compose)
```bash
# 1. Copy sample environment file and configure API keys
cp .env.example .env

# 2. Start the complete stack (Next.js frontend on 3000, FastAPI backend on 8000)
make up

# 3. Access the dashboard
open http://localhost:3000
```

### Local Development CLI
```bash
# Validate your candidate profile
job-butler profile validate

# Query screening answers
job-butler profile query "Are you authorized to work in India?"

# Scout fresh jobs matching your profile
job-butler scout run --limit 10

# Tailor a resume for a specific job
job-butler tailor --job-id <JOB_ID>
```

---

## Architecture & Roadmap

For complete system architecture and detailed slice blueprints, refer to:
- [docs/architecture.md](docs/architecture.md)
- [docs/slices/](docs/slices/)
- [AGENTS.md](AGENTS.md)

