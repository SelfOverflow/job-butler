# Slice 4: Real-Time Web Dashboard

## 1. Usable Product Delivered at Slice End
At the completion of Slice 4, you will have a working, browser-based command center for Job Butler:
- Run `job-butler serve --port 8000` $\rightarrow$ Launches the FastAPI + WebSocket dashboard at `http://localhost:8000`.
- Open `http://localhost:8000` in your browser to:
  * Browse all active jobs discovered by the scout.
  * View ATS match score badges and highlighted skills.
  * Download tailored PDF resumes directly with a single click.
  * Watch a live WebSocket event stream of new jobs and system actions.
  * Inspect your candidate profile, target roles, and screening answers.

```bash
# Example usable command right after Slice 4:
job-butler serve
# Output:
# [✓] Job Butler Web Dashboard live at: http://localhost:8000
# [✓] WebSocket event bus active at: ws://localhost:8000/ws/events
```

## 2. Components & Architecture
```
src/
├── server/
│   ├── app.py               # FastAPI application factory
│   ├── ws_manager.py        # WebSocket event bus (broadcasts events to open UI tabs)
│   ├── routes/
│   │   ├── api.py           # REST endpoints: GET /api/jobs, GET /api/profile
│   │   ├── artifacts.py     # Static file serving: GET /artifacts/resumes/{job_id}.pdf
│   │   └── hitl.py          # HITL actions placeholder (expanded in Slice 5)
│   └── templates/
│       └── index.html       # Responsive single-page dashboard (HTML5 + Tailwind CSS + WebSockets)
└── cli_serve.py             # Subcommand: `job-butler serve`
```

## 3. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice4_server.py`:

1. `test_server_health_check()`:
   - Queries `GET /health`; asserts status `ok`.
2. `test_list_jobs_api()`:
   - Populates test SQLite database; queries `GET /api/jobs`.
   - Asserts response contains active jobs, match scores, and resume links.
3. `test_download_tailored_pdf_endpoint()`:
   - Creates a mock PDF in artifacts directory; queries `GET /artifacts/resumes/test_job.pdf`.
   - Asserts HTTP 200 with `application/pdf` content-type header.
4. `test_websocket_live_event_broadcast()`:
   - Connects to `/ws/events` via `TestClient.websocket_connect()`.
   - Triggers a system event; asserts client receives formatted JSON payload within timeout.
5. `test_cli_serve_command()`:
   - Verifies CLI entrypoint starts uvicorn with correct host, port, and reload flags.

## 4. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice4*`
- [ ] Clean type annotations with `mypy --strict src/server`
- [ ] Dashboard accessible at `http://localhost:8000` with sub-100ms load time.
- [ ] Live WebSocket event stream functions across multiple open browser tabs.
