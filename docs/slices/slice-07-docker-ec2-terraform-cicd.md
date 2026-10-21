# Slice 7: Dockerization, Low-Cost EC2 Terraform & CI/CD

## 1. Usable Product Delivered at Slice End
At the completion of Slice 7, you will have a containerized, 1-click deployable platform ready for both local 24/7 execution and automated AWS deployment:
- Run `make up` (or `docker compose up -d`) $\rightarrow$ Instantly starts the entire Job Butler stack locally inside Docker (Web Dashboard + Autopilot Daemon + Playwright + Typst) with persistent `./data` and `./artifacts` volumes.
- Run `make test` $\rightarrow$ Executes the full TDD test matrix (`ruff`, `mypy --strict`, `pytest --cov`).
- Run `cd terraform && terraform apply` $\rightarrow$ Automates complete AWS cloud deployment to a low-cost EC2 instance (`t4g.small` / `t3.micro`, ~$3–$8/mo or $0 Free Tier), provisions an attached persistent EBS volume, and starts the container.
- Push code to GitHub $\rightarrow$ Automated GitHub Actions CI/CD tests the codebase and updates the EC2 instance with zero downtime.

```bash
# Example usable command right after Slice 7:
make up
# Output:
# [✓] Building container job-butler:latest (Python 3.11 + Playwright Chromium + Typst)
# [✓] Container job-butler-web started at http://localhost:8000
# [✓] Container job-butler-worker started (Autopilot daemon active)
```

## 2. Components & Architecture
```
job_butler/
├── Dockerfile               # Multi-stage image: Python 3.11, Playwright Chromium, Typst CLI
├── docker-compose.yml       # Local 24/7 orchestrator with persistent volume mounts
├── Makefile                 # Developer CLI: make up, make down, make test, make lint
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
        └── ssm/             # SSM Parameter Store for LLM & Firecrawl API keys
```

## 3. TDD & Infrastructure Validation Specification
Tests in `tests/integration/test_slice7_infra.py`:

1. `test_dockerfile_build_and_entrypoints()`:
   - Validates that the multi-stage Docker build succeeds and packages Python, Playwright Chromium, and the Typst CLI binary.
2. `test_docker_compose_environment_variables()`:
   - Verifies volume mappings for `./data` and `./artifacts` and port binding to `8000`.
3. `test_terraform_syntax_and_plan()`:
   - Runs `terraform validate` and `terraform plan` against a mock AWS provider; asserts valid resource graph and outputs.
4. `test_github_actions_workflow_syntax()`:
   - Validates `.github/workflows/ci.yml` and `deploy.yml` YAML syntax and step dependencies.

## 4. Acceptance Criteria
- [ ] `docker compose up --build -d` runs locally without errors.
- [ ] UI is reachable at `http://localhost:8000` with live autopilot daemon in the container.
- [ ] `terraform validate` and `terraform plan` execute cleanly.
- [ ] GitHub Actions CI workflow passes 100% on master.
