# Slice 3: AI Resume Tailor & ATS Scorer CLI

## 1. Usable Product Delivered at Slice End
At the completion of Slice 3, you will have a working resume tailoring engine that executes a two-stage **Drafter-Reviewer** loop, enforces geographic page limits, formats an ATS-compliant Typst PDF, and verifies the extracted text layer:
- Run `job-butler tailor --job-id <JOB_ID>` $\rightarrow$
  1. Analyzes the target JD and extracts 25–35 role-specific keywords.
  2. **Drafter Stage**: Selects matching atomic bullets from your 4 verified roles.
  3. **Reviewer Stage**: Checks for zero hallucination, confirms verbatim LinkedIn URL, and enforces page budget (1 page for India, 2 pages for International).
  4. **Compilation**: Builds ATS-clean single-column PDF via Typst and plain `.txt` cover letter.
  5. **Text-Layer Verification**: Extracts PDF text via `pypdf`/`pdftotext` to confirm 100% parseability and keyword coverage.
- Run `job-butler tailor --all-matches --min-score 75` $\rightarrow$ Batches tailoring for all eligible active jobs.
- Run `job-butler tailor verify-pdf <PATH>` $\rightarrow$ Runs ATS text layer check on any compiled PDF.

```bash
# Example usable command right after Slice 3:
job-butler tailor --job-id job_01
# Output:
# [✓] ATS Match Score: 94/100 (Tier 1 Domestic)
# [✓] Drafter: Selected 12 atomic bullets across OakNorth, Tejas, and Stepswatch
# [✓] Reviewer: 100% verified against profile (0 hallucinations, 1-page budget met)
# [✓] Typst compiled: ./artifacts/resumes/job_01_resume.pdf
# [✓] Text-Layer Check: 31/35 keywords matched, contact details in document body flow
# [✓] Plain text cover letter: ./artifacts/cover_letters/job_01_cover.txt
```

## 2. Core Tailoring & Verification Guardrails

### 2.1 Geographic Page Budgeting Rule
* **India Domestic Roles**: Exactly **1 page**.
* **International Relocation Roles**: Exactly **2 pages**.
* **Cover Letter**: Exactly **1 page** (generated in both PDF and clean line-broken `.txt` for web forms).

### 2.2 Mandatory Roles & Verbatim LinkedIn Rule
* **Mandatory Roles**: Every tailored CV must explicitly include all 4 positions:
  1. OakNorth India — Technical Lead (Individual Contributor) (Jul 2025 - Present)
  2. Tejas Networks Ltd — Senior Engineer (Apr 2024 - Jul 2025)
  3. Tejas Networks Ltd — Research & Development Engineer (Jul 2021 - Apr 2024)
  4. Stepswatch SASU — Frontend Developer Intern (Mar 2020 - May 2020)
* **Verbatim LinkedIn URL**: Always display `https://www.linkedin.com/in/mohit-ranjan-759188169` verbatim without trimming.
* **Standard ATS Headings**: Canonical headers only (`Professional Experience`, `Technical Skills`, `Education`, `Projects`, `Certifications`).

### 2.3 Two-Stage Drafter-Reviewer Pattern
* **Drafter**: Selects and ranks registered bullet IDs from `candidate_profile.yaml` matching JD keywords.
* **Reviewer**: Re-evaluates drafted markup against canonical profile facts; strips any unverified claims; verifies date formatting is strictly `Mon YYYY - Mon YYYY`.

### 2.4 Automated ATS Text-Layer Verification
Post-compilation validator extracts PDF text:
* Confirms text is 100% extractable (no empty PDF, no replacement glyphs).
* Verifies contact details appear as literal text in the main document flow.
* Confirms 25–35 exact JD keywords are present.

## 3. Components & Architecture
```
src/
├── agents/
│   └── tailor/
│       ├── client.py        # LLM client (Gemini / OpenAI / Anthropic)
│       ├── drafter.py       # Atomic bullet selection and keyword alignment
│       ├── reviewer.py      # Zero-hallucination auditor and constraint checker
│       ├── typst_engine.py  # Typst template renderer and PDF compiler
│       ├── pdf_verifier.py  # ATS text-layer validator (pypdf / pdftotext)
│       └── cover_letter.py  # Generates 1-page cover letter (PDF + clean .txt)
├── templates/
│   ├── resume_domestic.typ     # 1-page single-column Typst template
│   ├── resume_international.typ# 2-page single-column Typst template
│   └── cover_letter.typ        # 1-page Typst cover letter template
└── cli_tailor.py            # Subcommands: `job-butler tailor`
```

## 4. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice3_tailor.py`:

1. `test_page_budget_selection_domestic_vs_international()`:
   - For an India role, asserts template selects 1-page layout; for an EU/UK role, asserts 2-page layout.
2. `test_mandatory_roles_included()`:
   - Verifies OakNorth, Tejas (both roles), and Stepswatch are present in all generated resumes.
3. `test_drafter_reviewer_zero_hallucination_gate()`:
   - Injects a fake bullet into drafter output; asserts reviewer catches and rejects it.
4. `test_typst_single_column_pdf_compilation()`:
   - Compiles template to PDF; asserts exit code 0 and valid `%PDF-` binary output.
5. `test_pdf_text_layer_verifier()`:
   - Extracts text from compiled PDF; asserts presence of verbatim LinkedIn URL and required tech keywords.
6. `test_cover_letter_txt_export()`:
   - Asserts generation of plain `.txt` cover letter with clean line breaks alongside PDF.

## 5. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_slice3*`
- [ ] Domestic resumes compile to exactly 1 page; international to 2 pages.
- [ ] Automated text-layer check verifies 100% ATS readability.
- [ ] CLI command `job-butler tailor --job-id <ID>` outputs verified PDF and text cover letter.
