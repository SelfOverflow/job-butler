# Slice 5: Real-Time UI Dashboard & Human Escalation Interface

## 1. Goal & Scope
Build a real-time web UI and API server powered by **FastAPI** and **WebSockets**. The dashboard gives immediate visibility into continuous agent operations, provides real-time event feeds, and offers an interactive Human-in-the-Loop (HITL) workspace to review and resolve jobs flagged for manual intervention.

## 2. Components & Architecture
```
src/
└── server/
    ├── __init__.py
    ├── app.py               # FastAPI application factory and route registration
    ├── ws_manager.py        # WebSocket connection manager and event broadcaster
    ├── routes/
    │   ├── api.py           # REST endpoints for jobs, metrics, and profile
    │   ├── hitl.py          # HITL actions: list pending, resolve, skip, assisted launch
    │   └── static.py        # Static assets and SPA HTML dashboard
    └── templates/
        └── index.html       # Modern responsive dashboard (Tailwind CSS + WebSocket client)
```

## 3. UI Dashboard Features
1. **Live Activity Ticker**: Real-time WebSocket stream displaying discovery, verification, tailoring, and application events.
2. **HITL Escalation Center**:
   - Card/table view of jobs requiring user intervention (Workday login, CAPTCHA, manual portal).
   - Display includes company, role title, direct URL, and reason for escalation.
   - One-click actions:
     * **Download Tailored Resume**: Instant access to the compiled PDF.
     * **Copy Answers**: Copy pre-drafted answers to clipboard.
     * **Mark as Applied**: Updates database state to `APPLIED`.
     * **Dismiss / Skip**: Updates state to `SKIPPED_MANUAL`.
3. **Pipeline Metrics Banner**:
   - Total Scraped $\rightarrow$ Active Live $\rightarrow$ ATS Matched $\rightarrow$ Auto-Applied $\rightarrow$ Pending Intervention.

## 4. TDD Test Specification (Red Phase)
The following tests will be constructed in `tests/unit/test_server.py` using `httpx.AsyncClient` and FastAPI's `TestClient`:

1. `test_server_health_probe()`:
   - Queries `GET /health` and asserts HTTP 200 `{"status": "ok"}`.
2. `test_websocket_event_broadcast()`:
   - Connects to `/ws/events` using `TestClient.websocket_connect()`.
   - Emits an internal application event and verifies the client receives the JSON payload.
3. `test_hitl_pending_queue_endpoint()`:
   - Populates database with jobs in `REQUIRES_HUMAN_INTERVENTION` state.
   - Queries `GET /api/hitl/pending` and asserts returned schema and counts.
4. `test_hitl_resolve_endpoint()`:
   - Calls `POST /api/hitl/{job_id}/resolve`.
   - Asserts job state in DB updates to `APPLIED` with timestamp, and a WebSocket event is broadcasted.
5. `test_hitl_skip_endpoint()`:
   - Calls `POST /api/hitl/{job_id}/skip`.
   - Asserts job state updates to `SKIPPED_MANUAL`.

## 5. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_server*`
- [ ] Dashboard accessible at `http://localhost:8000` with sub-100ms load time.
- [ ] Real-time updates push via WebSocket without requiring page reload.
- [ ] Clean type annotations with `mypy --strict src/server`.
