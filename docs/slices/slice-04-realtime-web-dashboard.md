# Slice 4: Real-Time Web Dashboard (Next.js + React + Tailwind CSS)

## 1. Usable Product Delivered at Slice End
At the completion of Slice 4, you will have a production-grade, responsive Web Dashboard built with **Next.js (App Router)**, **React.js**, and **Tailwind CSS**, with a lean single-port production runtime:
- Run `job-butler serve` $\rightarrow$ Launches on port `8000`. In production and container builds, FastAPI serves the pre-compiled Next.js static export (`frontend/out/`) directly on port `8000` alongside the REST and WebSocket endpoints, eliminating the Node.js server overhead and saving ~150MB of RAM.
- For local frontend development, `make dev-frontend` runs Next.js on port `3000` with hot module reloading (HMR) proxying API requests to `:8000`.
- Open `http://localhost:8000` (or `http://localhost:3000` in dev) to:
  * **Job Explorer**: Search, filter, and inspect all discovered postings with ATS match score badges and 1-click tailored PDF resume downloads.
  * **Interactive Profile & Preferences Editor (`/profile`)**: Edit candidate details, target roles, salary floors, skills, and screening questions with real-time schema validation and instant backup creation.
  * **Real-Time Live Feed**: Watch jobs being scouted, links verified, and resumes tailored via a resilient WebSocket stream with visual toast notifications.
  * **HITL Escalation Center (`/hitl`)**: Interface for jobs flagged for manual intervention.

```bash
# Example usable command right after Slice 4:
job-butler serve
# Output:
# [✓] Unified Job Butler Dashboard & API live at: http://localhost:8000
# [✓] WebSocket event bus connected: ws://localhost:8000/ws/events
```

## 2. Components & Architecture
```
job_butler/
├── frontend/                # Next.js + React + Tailwind CSS App
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.mjs
│   ├── app/
│   │   ├── layout.tsx       # Root layout with sidebar navigation & toast provider
│   │   ├── page.tsx         # Dashboard overview (metrics, live feed, stats)
│   │   ├── jobs/
│   │   │   └── page.tsx     # Filterable jobs table with ATS match badges & PDF downloads
│   │   ├── profile/
│   │   │   └── page.tsx     # Visual form & YAML profile editor with backup history
│   │   ├── audit/
│   │   │   └── page.tsx     # Centralized action audit log explorer & inspector
│   │   └── hitl/
│   │       └── page.tsx     # Intervention queue for blockers (login, CAPTCHA)
│   ├── components/
│   │   ├── Sidebar.tsx
│   │   ├── LiveFeed.tsx     # WebSocket streaming ticker
│   │   ├── JobCard.tsx      # Job card with ATS score pill and PDF link
│   │   ├── AuditLogViewer.tsx # Searchable, filterable audit log table with JSON drawer
│   │   ├── ProfileForm.tsx  # Form editor with Pydantic validation feedback
│   │   └── YamlEditor.tsx   # Raw YAML editor with validation & save
│   └── lib/
│       ├── api.ts           # Type-safe fetch client for FastAPI REST endpoints
│       └── websocket.ts     # WebSocket client with auto-reconnect
└── src/
    └── server/
        ├── app.py           # FastAPI application factory
        ├── ws_manager.py    # WebSocket broadcaster
        └── routes/
            ├── api.py       # REST endpoints: GET /api/jobs, GET /api/profile, PUT /api/profile
            ├── audit_api.py # Audit endpoints: GET /api/audit (filters by actor, action, status)
            └── artifacts.py # Static file delivery for compiled PDFs
```

## 2.1 Implementation Notes
* **Next.js 16** (current stable) instead of 14. `next.config.ts` enables `output: "export"` (with `trailingSlash`) only for production builds and the `/api` rewrite only in `next dev`, because static export and rewrites cannot be combined.
* **Live feed source**: `/ws/events` polls the `audit_logs` table (`EVENT_POLL_SECONDS`, default 2 s) and broadcasts new rows, so actions from the CLI or scheduler processes appear live. New connections receive a snapshot of the 20 latest events.
* **Profile editing**: the form sends only changed fields as `{"set": {...}}` (JSON-encoded YAML values); the raw editor sends `{"yaml": text}` saved verbatim. Both go through the backup + validation path, and 422 responses carry `[{loc, msg}]`.
* **Local only**: no authentication; `job-butler serve` binds to `127.0.0.1`. See slice 7 before any cloud deployment.

## 3. UI Styling & Theme
* **Framework**: React 18+ with Next.js 14+ App Router.
* **Styling**: Tailwind CSS with dark-mode support, modern card-based hierarchy, subtle borders, and accessible badges.
* **Icons**: `lucide-react` for clean, lightweight iconography.

## 4. TDD Red-Phase Test Specification
Tests are split between backend API contract tests and frontend component tests:

### Backend API Tests (`tests/unit/test_slice4_server.py`)
1. `test_server_health_check()`: Asserts `GET /health` returns HTTP 200 `ok`.
2. `test_get_profile_api()`: Asserts `GET /api/profile` returns canonical profile matching `candidate_profile.yaml`.
3. `test_put_profile_api_success()`: Updates preferences via `PUT /api/profile`; asserts HTTP 200, file updated, and backup saved.
4. `test_put_profile_api_validation_error()`: Injects malformed fields; asserts HTTP 422 with structured field errors.
5. `test_jobs_list_api()`: Asserts `GET /api/jobs` returns active jobs with match scores and PDF links.
6. `test_get_audit_logs_api()`: Asserts `GET /api/audit` returns paginated audit records with actor/status filtering.
7. `test_websocket_event_broadcasting()`: Connects to `/ws/events` and verifies JSON message delivery.

### Frontend Component Tests (`frontend/__tests__/`)
1. `JobCard.test.tsx`: Renders job card; asserts title, company, ATS score badge, and download link render correctly.
2. `AuditLogViewer.test.tsx`: Renders audit table; asserts actor tags, action badges, and drawer display for log JSON details.
3. `ProfileForm.test.tsx`: Simulates user changing minimum salary and clicking save; verifies `PUT /api/profile` is invoked.
4. `LiveFeed.test.tsx`: Simulates incoming WebSocket messages and verifies real-time list updates.

## 5. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice4*` and `npm test` in `frontend/`.
- [ ] Next.js app builds cleanly with `npm run build` with zero TypeScript or ESLint errors.
- [ ] Dashboard is fully responsive on desktop and mobile.
- [ ] WebSocket connection reconnects automatically on disconnection.
