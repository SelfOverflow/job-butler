# Slice 3: AI Resume Tailor & ATS Scorer CLI

## 1. Usable Product Delivered at Slice End
At the completion of Slice 3, you will have a working resume tailoring engine that takes any scouted job, evaluates your ATS match score, selects truthful atomic bullet points, and compiles a ready-to-submit, ATS-optimized PDF resume:
- Run `job-butler tailor --job-id <JOB_ID>` $\rightarrow$ Analyzes the target job description against your profile, computes an ATS match score (0–100), extracts keywords, selects the top matching atomic bullets (zero hallucination guarantee), and compiles an ATS-compliant PDF into `./artifacts/resumes/<JOB_ID>_resume.pdf`.
- Run `job-butler tailor --all-matches --min-score 75` $\rightarrow$ Batches tailoring for all active scouted jobs meeting your minimum score threshold.
- Run `job-butler tailor view-score <JOB_ID>` $\rightarrow$ Prints an ATS match breakdown (matched skills, missing skills, keyword frequency alignment).

```bash
# Example usable command right after Slice 3:
job-butler tailor --job-id job_01
# Output:
# [✓] ATS Match Score: 88/100
# [✓] Matched Skills: Python, FastAPI, Kafka, PostgreSQL, Distributed Systems
# [✓] Missing Skills: Kubernetes, Terraform
# [✓] Selected 6 atomic bullets from Stripe & VectorStream experiences
# [✓] Compiled ATS PDF: ./artifacts/resumes/job_01_resume.pdf
```

## 2. Components & Architecture
```
src/
├── agents/
│   └── tailor/
│       ├── client.py        # LLM client (Gemini / OpenAI / Anthropic via API keys)
│       ├── extractor.py     # ATS keyword and requirements parser
│       ├── selector.py      # Zero-hallucination atomic bullet ranker and validator
│       ├── typst_engine.py  # Typst template renderer and PDF compiler
│       └── prompt.py        # Tailoring prompts and structured JSON outputs
├── templates/
│   └── resume.typ           # Single-column ATS-standard Typst resume template
└── cli_tailor.py            # Subcommand: `job-butler tailor`
```

## 3. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice3_tailor.py`:

1. `test_ats_keyword_extraction()`:
   - Feeds a sample Backend Engineer JD; asserts extraction of required competencies.
2. `test_zero_hallucination_bullet_selector()`:
   - Verifies that returned bullet IDs are strictly validated against `candidate_profile.yaml`.
   - Rejects or strips any hallucinated bullet text not present in the master profile.
3. `test_typst_template_rendering()`:
   - Validates that template placeholders populate accurately with candidate name, contact, selected bullets, and skills.
4. `test_typst_binary_pdf_generation()`:
   - Compiles `.typ` file to `.pdf` and verifies the resulting file is a valid selectable-text PDF.
5. `test_cli_tailor_single_job_command()`:
   - Runs `job-butler tailor --job-id mock_01` with mock LLM client; verifies output PDF exists in artifacts directory.

## 4. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice3*`
- [ ] Typst compiler produces clean single-column PDF without errors.
- [ ] LLM calls use mocked responses during tests (fast and zero API costs).
- [ ] Generated PDF resume is immediately readable and ready to be submitted.
