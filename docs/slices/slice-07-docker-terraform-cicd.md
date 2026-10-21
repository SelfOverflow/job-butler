# Slice 7: Dockerization, Low-Cost EC2 Terraform & CI/CD

## 1. Goal & Scope
Standardize packaging, automated deployment, and continuous delivery across local machines and AWS. Deliver a multi-stage `Dockerfile`, a local `docker-compose.yml` for zero-cost operation, complete cost-optimized **Terraform** modules for AWS EC2, and **GitHub Actions** CI/CD workflows.

## 2. Components & Architecture
```
job_butler/
├── Dockerfile               # Multi-stage image: Python 3.11, Playwright Chromium, Typst
├── docker-compose.yml       # Local 24/7 orchestrator with persistent volume mounts
├── Makefile                 # Standardized entrypoints (make test, make up, make down)
├── .github/
│   └── workflows/
│       ├── ci.yml           # Runs lint, type checking, and pytest TDD suite
│       └── deploy.yml       # Builds container & deploys to EC2 on merge
└── terraform/
    ├── main.tf              # AWS provider and module orchestration
    ├── variables.tf         # Instance type (t4g.small/t3.micro), region, keypair
    ├── outputs.tf           # Public IP, UI URL, EBS volume ID
    └── modules/
        ├── ec2/             # EC2 instance, launch template, user_data, security group
        ├── ebs/             # Persistent EBS volume for SQLite & artifacts
        └── ssm/             # SSM Parameter Store for LLM API keys
```

## 3. Containerization Strategy
* **Base Image**: `python:3.11-slim`
* **Dependencies**:
  * Headless Playwright Chromium (`playwright install --with-deps chromium`)
  * Pre-compiled Typst CLI binary downloaded and placed in `/usr/local/bin/typst`
* **Entrypoint**: Dual-mode launcher running:
  1. FastAPI web server and WebSocket hub on port `8000`.
  2. Background daemon executing hourly ingestion, matching, and application cycles.

## 4. Cost-Effective Terraform Design
* **Instance**: `t4g.small` (ARM64 Graviton) or `t3.micro` (AWS Free Tier eligible).
* **Storage**: 10 GB gp3 EBS volume mounted at `/data` for SQLite and resume PDFs.
* **Secrets**: AWS SSM Parameter Store holds `GEMINI_API_KEY`, `OPENAI_API_KEY`, etc.
* **Estimated Cost**: **$0 – $6 / month** (zero GPU/Fargate waste).

## 5. GitHub Actions Workflows
1. **`ci.yml`**:
   - Runs on all pushes and PRs.
   - Steps: Checkout $\rightarrow$ Setup Python $\rightarrow$ Cache dependencies $\rightarrow$ Run `ruff check` $\rightarrow$ Run `mypy --strict` $\rightarrow$ Run `pytest --cov`.
2. **`deploy.yml`**:
   - Runs on merge to `master`.
   - Steps: Build Docker image $\rightarrow$ Push to GitHub Container Registry (`ghcr.io`) or AWS ECR $\rightarrow$ Deploy update to EC2 instance via SSH/AWS SSM Run Command.

## 6. Acceptance Criteria
- [ ] `docker compose up --build -d` runs locally and mounts volumes cleanly.
- [ ] UI is reachable at `http://localhost:8000` with active background worker.
- [ ] `terraform validate` and `terraform plan` run without syntax or provider errors.
- [ ] GitHub Actions workflows are verified and passing.
