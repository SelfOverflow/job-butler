# Job Butler: System Architecture & Implementation Roadmap

## 1. System Overview & Philosophy

**Job Butler** is an autonomous, 24/7 career automation platform engineered for high cost-efficiency and zero wasted resources:
1. **Local Environment**: Zero cloud costs. Runs via `docker compose` or directly with Python for local execution, local testing, and 24/7 operation on your home/office machine.
2. **Cost-Optimized AWS Cloud Environment**: Deployed on low-cost **EC2 instances** (e.g., `t4g.micro` / `t4g.small` Graviton or `t3.micro`), running Docker / Docker Compose. 
3. **External API-Based Intelligence & Ingestion**:
   - **Scraping**: Powered by the **Firecrawl API** (`FIRECRAWL_API_KEY`) to effortlessly bypass anti-bot defenses, handle JS-rendered portals, and scrape/crawl target job boards into clean markdown/structured data.
   - **LLM Operations**: All AI operations (resume tailoring, cover letter drafting, DOM reasoning) invoke external LLM APIs (Gemini, OpenAI, or Anthropic) via API keys passed through environment variables. No expensive self-hosted LLMs or GPU instances.
4. **Agent-Driven Codebase Design**: The repository is structured specifically so that coding AI agents can autonomously inspect, test, modify, and evolve the codebase with zero ambiguity—backed by strict typing, deterministic test fixtures, and comprehensive TDD suites.

---

## 2. Cost-Effective Dual-Runtime Architecture (Local & AWS EC2)

```mermaid
graph TD
    subgraph ContainerImage ["Standardized Container (job-butler:latest)"]
        FastAPIApp["FastAPI Dashboard & WebSocket API"]
        WorkerDaemon["Continuous Ingestion & Application Daemon"]
        PlaywrightChromium["Headless Chromium & Stealth Drivers"]
        TypstEngine["Typst Binary (ATS Resume Compiler)"]
    end

    subgraph ExternalAPIs ["External Cloud Services"]
        LLMAPI["External LLM APIs (Gemini / OpenAI / Anthropic)"]
        FirecrawlAPI["Firecrawl API (Anti-Bot Web Scraping & Crawling)"]
    end

    subgraph LocalRuntime ["Local Execution (docker compose)"]
        LocalCompose["docker compose up -d"]
        LocalVolDB[("SQLite Volume: ./data/job_butler.db")]
        LocalVolPDF[("Artifacts Volume: ./artifacts/")]
        LocalEnv[".env (API Keys & Local Config)"]
    end

    subgraph AWSRuntime ["Cost-Effective AWS Cloud (Terraform)"]
        EC2Instance["Low-Cost EC2 Instance (t4g.small / t3.micro)"]
        EBSVolume[("Persistent EBS / SQLite: /data/")]
        SSMParams["AWS SSM Parameter Store (API Keys)"]
        S3Bucket[("Amazon S3 (Optional Resume Backups)")]
    end

    ContainerImage --> LocalRuntime
    ContainerImage --> AWSRuntime
    LocalCompose --> LocalVolDB
    LocalCompose --> LocalVolPDF
    LocalCompose --> LocalEnv
    LocalCompose <-->|HTTPS API Calls| LLMAPI
    LocalCompose <-->|Scraping Jobs| FirecrawlAPI

    EC2Instance --> EBSVolume
    EC2Instance --> SSMParams
    EC2Instance --> S3Bucket
    EC2Instance <-->|HTTPS API Calls| LLMAPI
    EC2Instance <-->|Scraping Jobs| FirecrawlAPI
```

### Monthly Cost Comparison
* **Fargate / Managed ECS + ALB + RDS**: ~$50 – $100+/month.
* **Our Cost-Optimized EC2 Architecture**: **~$3 – $8/month** (or **$0** within AWS Free Tier for `t3.micro`, or ~$4/mo on `t4g.micro`/`t4g.small`).

---

## 3. Storage & Environment Abstraction Layer

| Component | Local Mode (`APP_ENV=local`) | AWS EC2 Mode (`APP_ENV=production`) |
| :--- | :--- | :--- |
| **Compute** | Local Host / Docker Engine | Single or Multi-Node EC2 (`t4g.small` / `t3.micro`) |
| **Scraping Provider** | Firecrawl API via `.env` (`FIRECRAWL_API_KEY`) | Firecrawl API via SSM / env (`FIRECRAWL_API_KEY`) |
| **LLM Provider** | External API via `.env` (`GEMINI_API_KEY`, etc.) | External API via SSM / EC2 env (`GEMINI_API_KEY`) |
| **Database** | SQLite (`sqlite:///data/job_butler.db`) | SQLite on persistent EBS volume (`/data/job_butler.db`) |
| **Artifacts** | Local filesystem (`./artifacts/resumes/`) | Persistent EBS + optional S3 backup |
| **Browser Runner** | Headless Playwright Chromium | Headless Playwright Chromium |
| **Resume Compiler** | Embedded Typst CLI | Embedded Typst CLI |
| **UI Dashboard** | `http://localhost:8000` | `http://<EC2_PUBLIC_IP>:8000` (or reverse proxy / Caddy with free Let's Encrypt SSL) |

---

## 4. Targeted AI Agents & Ingestion Guardrails Specification

### 4.1 Resume & Cover Letter Tailor Agent
* **Role**: Analyzes the active job description and generates an ATS-optimized resume and tailored cover letter.
* **Two-Stage Drafter-Reviewer Pattern**:
  * **The Drafter**: Consumes verified `atomic_bullets` from `candidate_profile.yaml` across all 4 mandatory roles (OakNorth, Tejas Senior Eng, Tejas R&D, Stepswatch) and aligns them with 25–35 exact JD keywords.
  * **The Reviewer**: Validates that zero unverified claims exist, ensures dates are normalized (`Mon YYYY - Mon YYYY`), and enforces the geographic page budget.
* **Geographic Page Budget Rule**:
  * **India Domestic**: Exactly 1 page.
  * **International Relocation**: Exactly 2 pages.
  * **Cover Letter**: Exactly 1 page (PDF + clean line-broken `.txt` for online form autofill).
* **Automated ATS Text-Layer Verification**:
  * Post-compilation step extracts the PDF text layer (`pypdf` / `pdftotext`) to confirm 100% extractable text, verbatim LinkedIn URL, and absence of CID replacement glitches.

### 4.2 Application Navigator Agent
* **Role**: Drives browser interactions across diverse and dynamic application portals.
* **Capabilities**:
  * Uses Playwright to load job application pages and extract form schemas.
  * Employs LLM DOM reasoning to match input fields with candidate profile data (e.g. mapping "Years of experience with backend frameworks" $\rightarrow$ `5`).
  * Uses pre-configured STAR stories from `candidate_profile.yaml` for behavioral application questions.
  * **Blocker Escalation**:
    * If the portal requires an account (e.g., Workday, Taleo), a CAPTCHA, or two-factor authentication, the agent pauses the workflow, screenshots the state, and posts an escalation event to the dashboard.
    * Once the user completes the account setup or solves the barrier on the dashboard, the agent resumes or marks the application completed.

### 4.3 Ingestion Guardrails & Sourcing Scope
* **Deep Live Link Verification**:
  * Ashby SPAs: verifies `window.__appData` payload for active posting.
  * Workday SPAs: checks `postingAvailable: true`.
  * All ATS: SmartRecruiters, Greenhouse, Lever, Workable, etc.
* **Employer Exclusions (Strict Auto-Purge)**:
  * Never scrapes or applies to: **OakNorth**, **Tejas Networks**, **Stepswatch**.
* **Market Sourcing Hierarchy Boost**:
  * Tier 1: India Domestic (Bengaluru / Remote India +5, Delhi NCR / Hyderabad / Pune / Mumbai +3).
  * Tier 2: EU & Nordics (Visa Sponsorship / EU Blue Card, +4).
  * Tier 3: GCC / Middle East (Visa Sponsorship, +2).
  * Tier 4: Worldwide Relocation & Global Remote.

---

## 5. Candidate Profile Data Structure

```yaml
# candidate_profile.yaml specification
personal_info:
  full_name: "Alex Doe"
  email: "alex.doe@example.com"
  phone: "+1-555-0199"
  location:
    city: "San Francisco"
    state: "CA"
    country: "USA"
    postal_code: "94105"
    timezone: "America/Los_Angeles"
  links:
    linkedin: "https://linkedin.com/in/alexdoe"
    github: "https://github.com/alexdoe"
    portfolio: "https://alexdoe.dev"
  work_authorization:
    authorized_countries: ["USA"]
    visa_sponsorship_required: false
    security_clearance: null

preferences:
  target_roles: ["Senior Backend Engineer", "Distributed Systems Engineer", "AI Platform Engineer"]
  target_locations: ["Remote", "San Francisco, CA", "New York, NY"]
  remote_policy: "remote_preferred" # remote_only | remote_preferred | hybrid | onsite
  min_base_salary: 160000
  currency: "USD"
  notice_period_days: 14
  excluded_companies: ["SpamCorp", "ShadyAgency"]
  excluded_keywords: ["Cryptocurrency", "Web3"]

skills_inventory:
  languages:
    - name: "Python"
      proficiency: "expert"
      years_of_experience: 6
      last_used_year: 2026
    - name: "Go"
      proficiency: "intermediate"
      years_of_experience: 2
      last_used_year: 2025
  frameworks_libraries:
    - name: "FastAPI"
      proficiency: "expert"
      years_of_experience: 4
    - name: "PyTorch"
      proficiency: "intermediate"
      years_of_experience: 2
  cloud_devops:
    - name: "Docker"
      proficiency: "advanced"
      years_of_experience: 5
    - name: "AWS (ECS, S3, RDS, Lambda)"
      proficiency: "advanced"
      years_of_experience: 4
  databases:
    - name: "PostgreSQL"
      proficiency: "advanced"
      years_of_experience: 5
    - name: "Redis"
      proficiency: "advanced"
      years_of_experience: 4

work_experience:
  - id: "exp_stripe_sr_eng"
    company: "Stripe"
    title: "Senior Backend Engineer"
    location: "San Francisco, CA (Remote)"
    start_date: "2023-01"
    end_date: null
    is_current: true
    summary: "Led high-throughput payments orchestration service scaling."
    atomic_bullets:
      - id: "b_stripe_1"
        text: "Architected event-driven payment reconciliation pipeline handling 15k TPS with 99.999% uptime."
        skills: ["Python", "FastAPI", "Kafka", "PostgreSQL", "Distributed Systems"]
        metrics:
          throughput_tps: 15000
          availability: "99.999%"
        tags: ["high_scale", "fintech", "backend", "concurrency"]
      - id: "b_stripe_2"
        text: "Reduced P99 query latency from 240ms to 42ms by migrating hot transaction caches to Redis Cluster."
        skills: ["Redis", "PostgreSQL", "Query Optimization"]
        metrics:
          latency_drop_ms: 198
        tags: ["performance", "caching", "database"]

projects:
  - id: "proj_vector_search"
    name: "VectorStream"
    repo_url: "https://github.com/alexdoe/vectorstream"
    live_url: "https://vectorstream.dev"
    summary: "Open-source real-time semantic search indexing engine."
    atomic_bullets:
      - id: "b_proj_1"
        text: "Built asynchronous hybrid vector retrieval engine indexing 2M embeddings per minute."
        skills: ["Go", "ChromaDB", "Docker", "gRPC"]
        metrics:
          indexing_rate: "2M/min"
        tags: ["vector_search", "open_source"]

education:
  - institution: "University of California, Berkeley"
    degree: "B.S."
    field_of_study: "Computer Science"
    start_date: "2016"
    end_date: "2020"
    gpa: "3.85"

screening_question_bank:
  - question_pattern: "(?i)years of experience with python"
    answer_type: "number"
    answer_value: 6
  - question_pattern: "(?i)authorized to work"
    answer_type: "boolean"
    answer_value: true
  - question_pattern: "(?i)require sponsorship"
    answer_type: "boolean"
    answer_value: false
  - question_pattern: "(?i)notice period"
    answer_type: "text"
    answer_value: "2 weeks"
  - question_pattern: "(?i)expected salary|compensation"
    answer_type: "number"
    answer_value: 175000
```

---

## 6. Real-Time UI Dashboard & Human-in-the-Loop Hub

* **Real-Time Stream**: Live updates showing scraped positions, live validation status, tailoring events, and application results.
* **HITL Escalation Center**:
  * Displays jobs requiring user action (portal login, CAPTCHA, MFA).
  * Direct access to one-click tailored resume download, copy-ready answers to screening questions, and a "Mark as Applied" button.
* **Upskilling & Trend Analytics**:
  * Aggregated hiring demand metrics across all ingested postings.
  * ROI-ranked recommendations highlighting skills that would unlock the highest number of eligible roles.

---

## 7. Cost-Effective Terraform & GitHub Actions CI/CD

### 7.1 Terraform Architecture (AWS EC2)
* **`ec2` module**:
  * Provisions a low-cost `t4g.small` (ARM64) or `t3.micro` EC2 instance.
  * Attaches an elastic IP and security group (ports 22, 80, 443, 8000).
  * Provisions an attached persistent EBS volume for SQLite database storage and resume artifacts.
  * `user_data` script installs Docker & Docker Compose and pulls the application container.
* **`ssm` module**:
  * Securely stores LLM API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, etc.) in AWS Systems Manager Parameter Store.
* **`s3` module (Optional)**:
  * Low-cost S3 bucket for cold-storage backups of generated resumes.

### 7.2 GitHub Actions Workflows
* **`ci.yml`**:
  * Triggered on every commit/PR: executes `ruff` linting, `mypy` strict type checks, and `pytest` TDD suite.
* **`deploy.yml`**:
  * Triggered on merge to `master`: builds the Docker image, tags and pushes to Amazon ECR (or GitHub Container Registry `ghcr.io`), and triggers a seamless container update on the EC2 instance via SSH/AWS SSM Run Command.

---

## 8. Incremental TDD Slice Delivery Roadmap (Usable Product at Every Step)

Every slice is implemented through the **Red $\rightarrow$ Green $\rightarrow$ Refactor** cycle, culminating in a concrete, runnable feature you can execute immediately:

* **[Slice 1: Candidate Profile & Config Core](slices/slice-01-profile-and-config.md)**
  * **Runnable Output**: `job-butler profile validate`, `job-butler profile query "screening question"`, and `job-butler profile export-master`.
  * Validates your profile schema, guarantees unique fact-hashed atomic bullets, and tests automated screening answers.
* **[Slice 2: Job Scout & Live Link Verifier CLI](slices/slice-02-ingestion-and-verification.md)**
  * **Runnable Output**: `job-butler scout run` and `job-butler scout list`.
  * Scrapes target jobs via Firecrawl and ATS feeds, checks active link liveness, deduplicates into SQLite, and displays active roles in a formatted terminal table.
* **[Slice 3: AI Resume Tailor & ATS Scorer CLI](slices/slice-03-tailor-agent.md)**
  * **Runnable Output**: `job-butler tailor --job-id <ID>`.
  * Evaluates ATS fit score, extracts JD keywords, selects verified atomic bullets (zero hallucinations), and compiles a ready-to-submit ATS PDF via Typst.
* **[Slice 4: Real-Time Web Dashboard](slices/slice-04-realtime-web-dashboard.md)**
  * **Runnable Output**: `job-butler serve` at `http://localhost:8000`.
  * Modern web UI streaming real-time WebSocket events, listing active jobs, displaying ATS match badges, and providing 1-click tailored PDF resume downloads.
* **[Slice 5: Auto-Apply Navigator & HITL Escalation](slices/slice-05-auto-apply-and-hitl.md)**
  * **Runnable Output**: `job-butler apply --job-id <ID>` & Web Dashboard HITL Queue.
  * Headless Playwright submits direct ATS forms with confirmation screenshots; automatically escalates account portals, CAPTCHAs, and 2FA to the Web Dashboard with 1-click resolution.
* **[Slice 6: 24/7 Autopilot Scheduler & Upskilling Insights](slices/slice-06-autopilot-and-upskilling.md)**
  * **Runnable Output**: `job-butler autopilot start` & `job-butler analytics report`.
  * 24/7 background worker running hourly cycles; real-time dashboard analytics displaying market demand heatmaps and mathematical upskilling recommendations.
* **[Slice 7: Dockerization, Low-Cost EC2 Terraform & CI/CD](slices/slice-07-docker-ec2-terraform-cicd.md)**
  * **Runnable Output**: `make up` (local Docker Compose) & `terraform apply` (AWS EC2 deployment).
  * Multi-stage `Dockerfile`, 1-click local Docker Compose, Terraform modules for low-cost EC2/EBS/SSM, and GitHub Actions automated CI/CD workflows.

