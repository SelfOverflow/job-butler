# Slice 5: Auto-Apply Navigator & HITL Escalation

## 1. Usable Product Delivered at Slice End
At the completion of Slice 5, you will have a working automated application engine with complete Human-in-the-Loop (HITL) support:
- Run `job-butler apply --job-id <JOB_ID>` $\rightarrow$ Launches headless Playwright to autofill direct ATS forms (Greenhouse, Lever, etc.), uploads your tailored PDF resume, answers screening questions from your profile, submits the application, and saves a confirmation screenshot.
- When an account creation prompt, CAPTCHA, or 2FA barrier is encountered:
  * The agent captures a screenshot of the blocker.
  * The job is automatically escalated to the **Pending Human Action** tab in your Web Dashboard.
  * The UI provides one-click copyable credentials, pre-filled screening answers, direct resume download, and a **"Mark as Applied"** button once you complete the portal registration.

```bash
# Example usable command right after Slice 5:
job-butler apply --job-id job_01
# Output:
# [✓] Navigating to Greenhouse application page: https://boards.greenhouse.io/...
# [✓] Mapped 8 form fields (Name, Email, Phone, LinkedIn, GitHub, Resume)
# [✓] Attached tailored resume: ./artifacts/resumes/job_01_resume.pdf
# [✓] Answered 3 screening questions
# [✓] Application submitted successfully! Screenshot saved: ./artifacts/proofs/job_01.png
```

## 2. Components & Architecture
```
src/
├── agents/
│   └── navigator/
│       ├── browser.py       # Strict Playwright lifecycle manager (timeout & zombie process guard)
│       ├── form_inspector.py# DOM form field extractor
│       ├── field_mapper.py  # Maps candidate data to detected input fields
│       ├── barrier_detector.py # Detects login walls, CAPTCHAs, and 2FA
│       └── runner.py        # Submission orchestrator
├── server/
│   └── routes/
│       └── hitl.py          # HITL actions: GET /api/hitl/pending, POST /resolve, POST /skip
└── cli_apply.py             # Subcommand: `job-butler apply`
```

### 2.1 Chromium Lifecycle & Anti-Zombie Guards
To ensure headless browser instances never leak memory or hang indefinitely on a 1GB/2GB EC2 or local host:
* **Strict Context Scoping**: Every navigation uses an isolated `async with async_playwright() as p:` context.
* **Hard Navigation Timeout**: Global navigation and action timeouts are set to 30 seconds (`page.set_default_navigation_timeout(30000)`).
* **Guaranteed Teardown**: An outer `try ... finally: await context.close(); await browser.close()` block ensures that crashes, network timeouts, or unhandled exceptions always terminate the underlying Chromium process.
* **Concurrency Ceiling**: A maximum of 1 active browser session is permitted simultaneously.

## 3. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice5_navigator.py` and `tests/integration/test_slice5_apply.py`:

1. `test_field_mapper_standard_inputs()`:
   - Evaluates input matching for text, dropdowns, radio buttons, and file attachments.
2. `test_barrier_detector_login_prompt()`:
   - Loads a mock portal requiring account creation; asserts `BarrierDetector.check()` returns `ACCOUNT_CREATION_REQUIRED`.
3. `test_barrier_detector_captcha()`:
   - Loads a mock portal with simulated captcha widget; asserts `CAPTCHA_DETECTED`.
4. `test_direct_greenhouse_form_submission()`:
   - Runs headless Playwright against a local mock Greenhouse form; asserts all fields are filled, resume file attached, and submission succeeds.
5. `test_hitl_resolve_and_skip_endpoints()`:
   - Calls `POST /api/hitl/{job_id}/resolve` and `POST /skip`; asserts database status updates and WebSocket event broadcasts.

## 4. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice5* tests/integration/test_slice5*`
- [ ] Browser tests run against local mock servers without flakiness (using Playwright locators).
- [ ] Direct forms submit seamlessly without human intervention.
- [ ] Account portals escalate cleanly into the Web Dashboard for one-click resolution.
