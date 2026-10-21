# Slice 6: 24/7 Autopilot Scheduler & Upskilling Insights

## 1. Usable Product Delivered at Slice End
At the completion of Slice 6, you will have a fully autonomous 24/7 background agent and an intelligent career advisory engine:
- Run `job-butler autopilot start --interval 60` $\rightarrow$ Runs continuously in the background, executing the entire cycle every 60 minutes:
  1. Scouts fresh job postings via Firecrawl and ATS feeds.
  2. Verifies live links and prunes expired roles.
  3. Tailors resumes for all matching roles.
  4. Auto-submits direct applications and alerts the HITL dashboard for accounts/CAPTCHAs.
  5. Aggregates hiring trend signals and calculates upskilling ROI.
- On the Web Dashboard (`http://localhost:8000`):
  * **Market Trends Panel**: Real-time frequency graphs of demanded skills across all target listings.
  * **Upskilling Recommendation Cards**: Shows high-ROI skills missing from your profile (e.g. *"Adding Kubernetes would unlock 14 matching roles (+28% uplift)"*).
- Run `job-butler analytics report` $\rightarrow$ Generates an instant terminal summary of your job search funnel and hiring trends.

```bash
# Example usable command right after Slice 6:
job-butler analytics report
# Output:
# ======================== Career Intelligence Report ========================
# Jobs Discovered: 142 | Active Live: 118 | Matched: 34 | Auto-Applied: 22
# Top Demanded Tech: Python (84%), Docker (62%), AWS (58%), Kubernetes (51%)
# Top Upskilling ROI:
#   1. Kubernetes: Unlocks 14 new roles (+28% eligibility)
#   2. Terraform:  Unlocks 8 new roles (+16% eligibility)
# ============================================================================
```

## 2. Components & Architecture
```
src/
├── scheduler/
│   ├── __init__.py
│   └── autopilot.py         # Async 24/7 loop orchestrating Scout -> Tailor -> Apply -> Analytics
├── analytics/
│   ├── aggregator.py        # Counts tech stack frequencies across postings
│   ├── skill_analyzer.py    # Analyzes gaps between profile and market demand
│   └── recommender.py       # Computes mathematical upskilling ROI
├── server/
│   └── routes/
│       └── analytics.py     # Endpoints: GET /api/analytics/trends, /api/analytics/upskill
└── cli_autopilot.py         # Subcommands: `job-butler autopilot start` & `job-butler analytics report`
```

## 3. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice6_autopilot.py` and `tests/unit/test_slice6_analytics.py`:

1. `test_autopilot_cycle_orchestration()`:
   - Mocks the scout, tailor, and apply stages; asserts the autopilot loop calls each stage in sequence with proper error handling and exponential jitter.
2. `test_skill_frequency_counter()`:
   - Feeds a batch of parsed postings; asserts accurate count of required technologies.
3. `test_upskilling_roi_math()`:
   - Verifies the ranking algorithm correctly scores missing skills based on role unlock counts.
4. `test_analytics_api_endpoints()`:
   - Queries `GET /api/analytics/trends` and `GET /api/analytics/upskill`; asserts schema conformity for UI charts.
5. `test_cli_analytics_report_command()`:
   - Executes `job-butler analytics report` via `CliRunner`; asserts tabular and summary display.

## 4. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice6*`
- [ ] Autopilot runs smoothly without memory leaks or runaway browser instances.
- [ ] Upskilling recommendations are backed by real database metrics (zero hallucination).
- [ ] Terminal and web analytics provide real-time visibility into hiring trends.
