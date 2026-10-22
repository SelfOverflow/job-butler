# Slice 8: Web Command Center (Every CLI Command from the Dashboard)

> **Delivery order:** after Slice 6 (autopilot), **before Slice 7 deployment**. When Job Butler is hosted online, the dashboard is the only interface, so everything the CLI can do must be available (and safe) from the browser first.

## 1. Usable Product Delivered at Slice End
At the completion of Slice 8, a candidate who never opens a terminal can operate the whole platform from the dashboard:
- **Command Center (`/run`)**: launch any operation with a parameter form, watch live progress bars (the same stages the CLI shows), cancel it, and read the result.
- **Contextual actions** where they belong: *Tailor* / *Prepare application* / *Re-verify link* buttons on each job card; *Validate* / *Export master resume* / *Test screening answer* on the Profile page; *Approve* / *Skip* / *Mark applied* on the HITL page (Slice 5).
- **Run history (`/runs`)**: every run with who started it, parameters, duration, status, summary, and errors; linked to the audit log.
- **Settings (`/settings`)**: shows which integrations are configured (Firecrawl, Gemini, model, credit budget used today) without ever revealing secret values.
- **Sign-in**: a single-user login protecting the UI, REST API, and WebSocket when hosted.

```text
Dashboard ─▶ "Run scout sweep (limit 20)" ─▶ live bars: Searching 6/6 · Boards 14/17 · Verifying 9/20
          ─▶ result: Discovered 412 · rejected 40 (experience 31, visa 9) · saved 19 (7 new)
```

## 2. CLI → Web Parity Map
| CLI command | Web equivalent | Execution |
| :--- | :--- | :--- |
| `scout run --limit N` | Command Center → *Scout sweep* | Background run (progress) |
| `scout verify` | Command Center → *Re-verify stored jobs*; per-job *Re-verify link* | Background run (progress) |
| `scout list` | `/jobs` (exists) | Read-only |
| `tailor --job-id ID` | Job card → *Tailor* | Background run |
| `tailor --all-matches --min-score N` | Command Center → *Tailor all matches* | Background run (progress) |
| `tailor verify-pdf PATH` | Job card → *Check PDF*; upload a PDF in Command Center | Synchronous |
| `apply --job-id ID` (prepare) | Job card → *Prepare application* | Background run (browser) |
| `apply approve ID` / skip / mark applied | `/hitl` actions (Slice 5) | Background run / synchronous |
| `profile validate` / `query "…"` / `export-master` | Profile page buttons; screening-answer tester | Synchronous |
| `profile update` / `add-bullet` / `backups` / `restore` | Profile form, YAML editor, backups (exist); *Add bullet* dialog | Synchronous |
| `profile init` | First-run onboarding: create profile from the template in the browser | Synchronous |
| `autopilot start/stop/status`, `analytics report` (Slice 6) | Command Center toggles + `/analytics` | Background / read-only |

New CLI commands must ship with their web equivalent from now on (enforced in `AGENTS.md`).

## 3. Architecture

### 3.1 Shared Service Layer (no shelling out)
```
src/services/
├── scout.py      # sweep(...), verify(...), prune(...)   ← called by cli_scout.py AND the API
├── tailor.py     # tailor_one(...), tailor_matches(...), check_pdf(...)
├── apply.py      # prepare(...), approve(...), skip(...), mark_applied(...)
└── profile.py    # validate(...), export_master(...), query(...), init_from_template(...)
```
* CLI modules become thin wrappers (parse args → service → print). The server **never** spawns `job-butler` subprocesses; it calls the same functions, so CLI and web behaviour cannot drift.
* Services accept a `ProgressFn` and a `CancelToken`, return typed result dataclasses, and raise typed errors (`ProfileError`, `TailorError`, …) that both front ends render.

### 3.2 Background Command Runner
```
src/server/runner.py   # in-process executor + run registry
src/server/routes/commands.py
```
* `POST /api/commands/{name}` with a JSON body validated per command → `202 {"run_id": …}`.
* A single worker thread executes runs **one at a time** (SQLite single-writer, 1-browser ceiling from Slice 5); additional requests queue. Starting a command that is already queued/running returns the existing run (single-flight).
* `command_runs` table: `id, command, params JSON, status (queued|running|succeeded|failed|cancelled), progress JSON {stage, done, total, detail}, result JSON, error, requested_by, created_at, started_at, finished_at`.
* Progress callbacks update the run row (throttled to ~4/s) and broadcast `{"type": "command", "run": …}` on `/ws/events` alongside audit events.
* `POST /api/commands/runs/{id}/cancel` sets the cancel token; services check it between steps (between queries, boards, verifications, jobs).
* Every run writes `COMMAND_STARTED` / `COMMAND_FINISHED` audit events with `actor=human:user` (or `agent:autopilot`).
* On server restart, runs left `running` are marked `failed` ("interrupted by restart").

### 3.3 Authentication & Hardening (required for online hosting)
* **Single-user login**: password hash (`argon2`) from `DASHBOARD_PASSWORD_HASH` (env locally, SSM in AWS). `POST /api/auth/login` sets an `HttpOnly; Secure; SameSite=Strict` session cookie (signed, 12 h expiry); `POST /api/auth/logout`.
* All `/api/*` routes and `/ws/events` require the session; static assets and `/health` stay public.
* **CSRF**: state-changing requests require a double-submit token header (`X-CSRF-Token`).
* **Rate limiting**: login attempts limited per IP (e.g. 5/min) with backoff.
* **Local mode**: `AUTH_DISABLED=true` is allowed only when bound to `127.0.0.1`; the server refuses to start with auth disabled on any other interface.
* Secrets are never returned by any endpoint; `/api/settings` reports only `configured: true/false` and non-secret values (model name, credit budget, credits used today).

### 3.4 Frontend
```
frontend/app/run/page.tsx         # Command Center: command cards + parameter forms + live runs
frontend/app/runs/page.tsx        # Run history with result/error drawer
frontend/app/settings/page.tsx    # Integration status (no secrets)
frontend/app/login/page.tsx       # Sign-in
frontend/components/CommandCard.tsx    # Params form, Run/Cancel, live StageBars
frontend/components/StageBars.tsx      # Progress bars mirroring CLI stages
frontend/components/RunDrawer.tsx      # Params, timeline, result summary, error
frontend/lib/commands.ts               # Typed command catalogue + client
```
* Job cards gain *Tailor*, *Prepare application*, *Re-verify* buttons that start runs and show inline progress.
* Profile page gains *Validate*, *Export master resume* (download), *Test screening answer*, *Add bullet*.
* Destructive or outward-facing actions (approve/submit an application, restore a backup, tailor all matches) show a confirmation dialog summarising the effect.

## 4. TDD Red-Phase Test Specification
### Backend (`tests/unit/test_slice8_*.py`, `tests/integration/test_slice8_*.py`)
1. `test_cli_and_api_call_the_same_service()`: CLI command and API route produce identical results for the same inputs (service function patched and asserted called).
2. `test_command_run_lifecycle()`: `POST /api/commands/scout_sweep` → queued → running → succeeded; progress persisted; result summary matches the service result.
3. `test_runs_execute_one_at_a_time_and_single_flight()`: concurrent requests queue; duplicate request returns the existing run.
4. `test_cancel_running_command()`: cancel token stops the service between steps; status `cancelled`.
5. `test_command_progress_broadcast_over_websocket()`: `{"type": "command"}` messages arrive with stage/done/total.
6. `test_interrupted_runs_marked_failed_on_startup()`.
7. `test_command_params_validated()`: bad params → 422 with field errors; unknown command → 404.
8. `test_auth_required_for_api_and_websocket()`: 401 without session; login sets cookie; logout clears it; wrong password rate-limited.
9. `test_csrf_required_for_mutations()`.
10. `test_auth_disabled_only_on_localhost()`: startup refuses `AUTH_DISABLED` with a non-loopback host.
11. `test_settings_never_expose_secrets()`.

### Frontend (`frontend/__tests__/`)
1. `CommandCard.test.tsx`: fills params, starts a run (POST body asserted), renders live stage bars from WebSocket messages, cancel button.
2. `RunsPage.test.tsx`: lists runs, drawer shows params/result/error.
3. `JobCardActions.test.tsx`: *Tailor* / *Prepare application* start runs and show inline status.
4. `LoginPage.test.tsx`: submits credentials, handles 401 and rate-limit messages, redirects on success.
5. `ConfirmDialog.test.tsx`: outward-facing actions require confirmation.

## 5. Incremental Delivery Plan (~300 LOC each)
1. Service layer extraction for profile + scout (CLI rewired, behaviour unchanged, tests green).
2. Service layer for tailor + apply.
3. `command_runs` table, runner (queue, single-flight, cancel, restart recovery), `/api/commands` routes.
4. WebSocket command broadcasts + throttled progress persistence.
5. Auth: login/logout, session cookie, CSRF, rate limit, loopback-only `AUTH_DISABLED`, WebSocket auth.
6. Frontend: command catalogue client, `CommandCard`, `StageBars`, `/run`.
7. Frontend: `/runs` history + drawer, `/settings`, `/login`.
8. Frontend: contextual actions on Jobs, Profile, and HITL pages with confirmation dialogs.

## 6. Acceptance Criteria
- [ ] Every CLI command in the parity map is operable from the dashboard.
- [ ] CLI and web share one service layer; no subprocess execution of `job-butler` by the server.
- [ ] Long-running commands show live progress and can be cancelled; runs are recorded and audited.
- [ ] With auth enabled, no API route or WebSocket is reachable without a session; auth cannot be disabled on a public interface.
- [ ] No endpoint returns secret values.
- [ ] 100% pass rate for `test_slice8*` and frontend tests; `npm run build` has zero TypeScript/ESLint errors.
