# Slice 7: Dockerization, Low-Cost EC2 Terraform & CI/CD

## 1. Usable Product Delivered at Slice End
At the completion of Slice 7, you will have a containerized, 1-click deployable platform ready for both local 24/7 execution and automated AWS deployment:
- Run `make up` (or `docker compose up -d`) $\rightarrow$ Starts the lean Job Butler stack inside Docker on a single unified port `8000`:
  * **Unified Server (FastAPI :8000)**: Serves both the compiled Next.js static export (`frontend/out`) and all REST/WebSocket APIs with zero Node.js server overhead.
  * **Autopilot Worker Daemon**: Runs in background orchestrating hourly cycles.
  * **Playwright Chromium & Typst Engine**: Bundled and managed with strict lifecycle cleanups.
  * Mounted persistent volumes for SQLite WAL database (`./data`) and resumes/artifacts (`./artifacts`).
- Run `make test` $\rightarrow$ Executes the full TDD test matrix (backend `pytest`, frontend `npm test`, `mypy --strict`, `ruff`).
- Run `cd terraform && terraform apply` $\rightarrow$ Automates complete AWS deployment to a low-cost EC2 instance (`t4g.small` / `t3.micro`, ~$3–$8/mo or $0 Free Tier), provisions an attached persistent EBS volume, and starts the container stack on port 8000.
- Push code to GitHub $\rightarrow$ Automated GitHub Actions CI/CD tests the codebase and updates the EC2 instance with zero downtime.

```bash
# Example usable command right after Slice 7:
make up
# Output:
# [✓] Building multi-stage container (Next.js static export + FastAPI + Playwright + Typst)
# [✓] Container job-butler live at http://localhost:8000 (UI + API + Worker active)
```

## 2. Components & Architecture
```
job_butler/
├── Dockerfile               # Multi-stage image: Next.js static export + Python 3.11 + Playwright + Typst
├── docker-compose.yml       # Local 24/7 single-container runner (UI + API + worker on :8000, volumes)
├── Makefile                 # Developer CLI: make up, make down, make test, make lint
├── frontend/                # Next.js 14 App Router + Tailwind CSS
├── src/                     # Python core backend, agents, scheduler
├── .github/
│   └── workflows/
│       ├── ci.yml           # Runs Python and Next.js test matrices
│       └── deploy.yml       # Builds container & deploys to EC2 on merge
└── terraform/
    ├── main.tf              # AWS provider and module orchestration
    ├── variables.tf         # Instance type (t4g.small/t3.micro), region, keypair
    ├── outputs.tf           # Public IP, UI URL, EBS volume ID
    └── modules/
        ├── ec2/             # EC2 instance, launch template, user_data, security group
        ├── ebs/             # Persistent EBS volume for SQLite & artifacts
        ├── cloudwatch/      # CloudWatch Log Group (/job-butler/production) & Metric Error Alarm
        └── ssm/             # SSM Parameter Store for LLM & Firecrawl API keys
```

## 3. Containerization Strategy
* **Frontend**: Built in a Node build stage via Next.js `output: 'export'`; only the static `frontend/out/` is copied into the final image and served by FastAPI (no Node.js runtime).
* **Backend**: Multi-stage `python:3.11-slim` with:
  * Headless Playwright Chromium (`playwright install --with-deps chromium`)
  * Pre-compiled Typst CLI binary in `/usr/local/bin/typst`
* **Local Compose**:
  * Runs a single `job-butler` service on port 8000 (UI + REST + WebSockets + autopilot worker).
  * Direct volume mounts for `./data` (SQLite database) and `./artifacts` (PDF resumes).

## 4. TDD & Infrastructure Validation Specification
Tests in `tests/integration/test_slice7_infra.py`:

1. `test_dockerfile_build_and_entrypoints()`:
   - Validates that the multi-stage Docker build succeeds and the image contains `frontend/out/`, Playwright Chromium, and Typst.
2. `test_docker_compose_environment_variables()`:
   - Verifies volume mappings for `./data` and `./artifacts` and a single port binding to `8000`.
3. `test_terraform_syntax_and_plan()`:
   - Runs `terraform validate` and `terraform plan` against a mock AWS provider; asserts valid resource graph and outputs.
4. `test_github_actions_workflow_syntax()`:
   - Validates `.github/workflows/ci.yml` and `deploy.yml` YAML syntax and test step dependencies.

## 5. Acceptance Criteria
- [ ] `docker compose up --build -d` runs locally without errors.
- [ ] Dashboard, API, and WebSockets reachable at `http://localhost:8000`.
- [ ] `terraform validate` and `terraform plan` execute cleanly.
- [ ] GitHub Actions CI workflow passes 100% on main.
