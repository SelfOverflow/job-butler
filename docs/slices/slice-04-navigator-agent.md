# Slice 4: Application Navigator Agent & HITL Escalation

## 1. Goal & Scope
Implement browser automation for job submissions. The Application Navigator Agent uses Playwright to navigate application portals, inspect form fields, map candidate answers, upload the tailored PDF, and cleanly distinguish between direct one-click forms and portals requiring human intervention (account creation, CAPTCHAs, MFA).

## 2. Components & Architecture
```
src/
└── agents/
    └── navigator/
        ├── __init__.py
        ├── browser.py       # Playwright context manager with stealth flags
        ├── form_inspector.py# DOM form field extractor and classifier
        ├── field_mapper.py  # Maps candidate profile & screening answers to form inputs
        ├── barrier_detector.py # Detects login walls, CAPTCHAs, and multi-factor prompts
        ├── runner.py        # Submission orchestrator
        └── exceptions.py    # BarrierDetectedException, FormFillException
```

## 3. Human-in-the-Loop Escalation Logic
* **Tier 1 (Direct Submission - Greenhouse / Lever / Workable)**:
  * Automatically populates standard fields (Name, Email, Phone, LinkedIn, GitHub).
  * Attaches tailored PDF resume from `artifacts/resumes/<job_id>.pdf`.
  * Answers screening questions using regex matcher from `screening.py`.
  * Submits form, captures confirmation screenshot, and logs status `APPLIED`.
* **Tier 2 (Barrier Escalation - Workday / Taleo / Login / CAPTCHA)**:
  * Detects account creation form (`<input type="password">`, "Create an account to apply", CAPTCHA iframe).
  * Takes a screenshot of the blocker page.
  * Emits an escalation event with direct URL, tailored resume path, and pre-drafted answers.
  * Sets status to `REQUIRES_HUMAN_INTERVENTION`.

## 4. TDD Test Specification (Red Phase)
All browser tests will execute against local HTML mock fixtures served by an ephemeral `aiohttp` or `httpx` server:

1. `test_field_mapper_standard_inputs()`:
   - Evaluates input matching for text, dropdowns, radio buttons, and checkboxes.
2. `test_barrier_detector_login_wall()`:
   - Loads a mock portal requiring account creation.
   - Asserts `BarrierDetector.check()` returns `BarrierType.ACCOUNT_CREATION_REQUIRED`.
3. `test_barrier_detector_captcha()`:
   - Loads a mock portal containing a simulated reCAPTCHA/Turnstile widget.
   - Asserts `BarrierDetector.check()` returns `BarrierType.CAPTCHA_DETECTED`.
4. `test_direct_greenhouse_form_submission()`:
   - Runs headless Playwright against a mock Greenhouse form.
   - Asserts all fields are filled, resume file attached, and submission succeeds.
5. `test_escalation_event_packaging()`:
   - Asserts escalation record contains screenshot path, candidate answers, and job metadata.

## 5. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_navigator*`
- [ ] Tested against local mock pages without flakiness (no arbitrary sleeps; use Playwright locators with explicit expect conditions).
- [ ] Non-blocking execution: runs headless by default with configurable `HEADLESS=false` for local debugging.

