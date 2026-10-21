# Slice 6: Analytics, Market Trends & Upskilling Engine

## 1. Goal & Scope
Build an intelligence layer that aggregates hiring signals across all ingested postings, analyzes skill demand distributions, and provides mathematically grounded upskilling recommendations showing which missing competencies will unlock the most matching roles.

## 2. Components & Architecture
```
src/
└── analytics/
    ├── __init__.py
    ├── aggregator.py        # Counts tech stack frequencies across postings
    ├── skill_analyzer.py    # Identifies gap between candidate profile and market demand
    ├── recommender.py       # Calculates potential match uplift per missing skill (ROI)
    └── report.py            # Generates daily/weekly summaries for the UI dashboard
```

## 3. Mathematical Upskilling ROI Model
For each missing skill $s \notin \text{CandidateSkills}$:
$$\text{Unlock Score}(s) = \sum_{j \in \text{UnmatchedJobs}} \mathbb{I}(s \in \text{JobKeywords}_j \land \text{Score}(j \cup \{s\}) \ge \text{Threshold})$$
$$\text{Projected Uplift Percentage} = \frac{\text{Unlock Score}(s)}{\text{Total Active Jobs}} \times 100\%$$

## 4. TDD Test Specification (Red Phase)
Tests will be constructed in `tests/unit/test_analytics.py`:

1. `test_skill_frequency_aggregation()`:
   - Feeds a batch of 10 parsed job postings with diverse requirements.
   - Asserts correct occurrence counts for keywords (`Python`: 8, `Kubernetes`: 6, `Go`: 4).
2. `test_gap_analysis_against_candidate_profile()`:
   - Compares candidate skills against job requirements.
   - Asserts exact partition into `matched_skills` and `missing_skills`.
3. `test_upskilling_roi_scoring()`:
   - Simulates 5 roles just below the match threshold (e.g. 68% when 70% is required) due to missing `Kubernetes`.
   - Asserts `recommender.get_recommendations()` ranks `Kubernetes` as #1 with an uplift count of 5 roles.
4. `test_analytics_summary_endpoint()`:
   - Queries `GET /api/analytics/trends` and `GET /api/analytics/upskilling`.
   - Asserts response structure conforms to expected JSON schema for UI charts.

## 5. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_analytics*`
- [ ] Deterministic mathematical calculations with zero hallucination.
- [ ] UI receives structured trend and upskilling data via REST/WebSocket.
- [ ] Strict type checking passes with `mypy --strict src/analytics`.

