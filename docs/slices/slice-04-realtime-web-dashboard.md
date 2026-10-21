# Slice 4: Real-Time Web Dashboard & Interactive Profile Editor

## 1. Usable Product Delivered at Slice End
At the completion of Slice 4, you will have a working, browser-based command center for Job Butler:
- Run `job-butler serve --port 8000` $\rightarrow$ Launches the FastAPI + WebSocket dashboard at `http://localhost:8000`.
- Open `http://localhost:8000` in your browser to:
  * **Interactive Profile & Preferences Editor**: View and edit your candidate profile, target roles, salary floors, skills, and screening questions directly in the browser with live schema validation and automatic backup creation on save.
  * Browse all active jobs discovered by the scout.
  * View ATS match score badges and highlighted skills.
  * Download tailored PDF resumes directly with a single click.
  * Watch a live WebSocket event stream of new jobs and system actions.

```bash
# Example usable command right after Slice 4:
job-butler serve
# Output:
# [✓] Job Butler Web Dashboard live at: http://localhost:8000
# [✓] WebSocket event bus active at: ws://localhost:8000/ws/events
# [✓] Interactive Profile Editor active at: http://localhost:8000/#/profile
```

## 2. Components & Architecture
```
src/
├── server/
│   ├── app.py               # FastAPI application factory
│   ├── ws_manager.py        # WebSocket event bus (broadcasts events to open UI tabs)
│   ├── routes/
│   │   ├── api.py           # REST endpoints: GET /api/jobs, GET /api/profile
│   │   ├── profile_api.py   # Profile endpoints: GET /api/profile, PUT /api/profile, GET /api/profile/backups
│   │   ├── artifacts.py     # Static file serving: GET /artifacts/resumes/{job_id}.pdf
│   │   └── hitl.py          # HITL actions placeholder (expanded in Slice 5)
│   └── templates/
│       └── index.html       # Responsive single-page dashboard with Profile Editor (HTML5 + Tailwind CSS + WebSockets)
└── cli_serve.py             # Subcommand: `job-butler serve`
```

## 3. Profile Editor Capabilities
1. **Visual Form & Raw YAML View**: Switch between structured form inputs (Target Roles, Salary, Notice Period, Skills) and raw YAML with syntax highlighting.
2. **Pre-Save Schema Validation**: FastAPI / Pydantic validates submissions before writing to disk, preventing syntax errors or broken models.
3. **Automated Backup & Revert**: Every update creates a snapshot in `profile/backups/`. The UI allows 1-click reversion to any prior version.
4. **Live Event Notification**: On successful save, an event is broadcasted over WebSockets to alert any background workers to reload the profile.

## 4. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice4_server.py`:

1. `test_server_health_check()`:
   - Queries `GET /health`; asserts status `ok`.
2. `test_get_profile_api()`:
   - Queries `GET /api/profile`; asserts JSON representation matches `candidate_profile.yaml`.
3. `test_put_profile_api_success()`:
   - Sends valid updated preferences payload to `PUT /api/profile`.
   - Asserts HTTP 200, profile updated on disk, and backup created in `profile/backups/`.
4. `test_put_profile_api_invalid_payload_rejected()`:
   - Sends payload missing mandatory fields; asserts HTTP 422 Unprocessable Entity and profile on disk remains unchanged.
5. `test_list_jobs_api()`:
   - Populates test SQLite database; queries `GET /api/jobs`.
   - Asserts response contains active jobs, match scores, and resume links.
6. `test_websocket_live_event_broadcast()`:
   - Connects to `/ws/events` via `TestClient.websocket_connect()`.
   - Updates profile or triggers event; asserts client receives formatted JSON payload within timeout.

## 5. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice4*`
- [ ] Clean type annotations with `mypy --strict src/server`
- [ ] Profile can be edited and saved via the Web UI with instant validation.
- [ ] Live WebSocket event stream functions across multiple open browser tabs.
