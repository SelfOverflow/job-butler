# Slice 3: AI Resume Tailor & ATS Scorer CLI

## 1. Usable Product Delivered at Slice End
At the completion of Slice 3, you will have a working resume tailoring engine that executes a two-stage **Drafter-Reviewer** loop, enforces geographic page limits, formats an ATS-compliant Typst PDF, and verifies the extracted text layer:
- Run `job-butler tailor --job-id <JOB_ID>` $\rightarrow$
  1. Analyzes the target JD and extracts 25–35 role-specific keywords.
  2. **Drafter Stage**: Selects matching atomic bullets from every role in `work_experience`.
  3. **Reviewer Stage**: Checks for zero hallucination, confirms verbatim LinkedIn URL, and enforces page budget (1 page for domestic Tier 1, 2 pages for international).
  4. **Compilation**: Builds ATS-clean single-column PDF via Typst and plain `.txt` cover letter.
  5. **Text-Layer Verification**: Extracts PDF text via `pypdf`/`pdftotext` to confirm 100% parseability and keyword coverage.
- Run `job-butler tailor --all-matches --min-score 75` $\rightarrow$ Batches tailoring for all eligible active jobs.
- Run `job-butler tailor verify-pdf <PATH>` $\rightarrow$ Runs ATS text layer check on any compiled PDF.

```bash
# Example usable command right after Slice 3:
job-butler tailor --job-id job_01
# Output:
# [✓] ATS Match Score: 94/100 (Tier 1 Domestic)
# [✓] Drafter: Selected 12 atomic bullets across all 4 roles
# [✓] Reviewer: 100% verified against profile (0 hallucinations, 1-page budget met)
# [✓] Typst compiled: ./artifacts/resumes/job_01_resume.pdf
# [✓] Text-Layer Check: 31/35 keywords matched, contact details in document body flow
# [✓] Plain text cover letter: ./artifacts/cover_letters/job_01_cover.txt
```

## 2. Core Tailoring & Verification Guardrails

### 2.1 Geographic Page Budgeting Rule
* **Domestic Roles (Tier 1)**: Exactly **1 page**.
* **International Relocation Roles**: At most **2 pages** (lowest-ranked bullets are dropped until the PDF fits; never a role's last bullet).
* **Cover Letter**: Exactly **1 page** (generated in both PDF and clean line-broken `.txt` for web forms).

### 2.2 Mandatory Roles & Verbatim LinkedIn Rule
* **Mandatory Roles**: Every tailored CV must include every entry in `work_experience` (no role is ever dropped; the Drafter only chooses which bullets to show per role).
* **Verbatim LinkedIn URL**: Always display `personal_info.links.linkedin` verbatim without trimming.
* **Standard ATS Headings**: Canonical headers only (`Professional Experience`, `Technical Skills`, `Education`, `Projects`, `Certifications`).

### 2.3 Two-Stage Drafter-Reviewer Pattern
* **Drafter (Gemini, `GEMINI_MODEL`, default `gemini-3.8-flash`)**: Returns only JD keywords and ranked bullet IDs. It never writes resume text; the JD is fenced as untrusted input.
* **Reviewer (deterministic)**: Unknown bullet IDs are hallucinations and rejected (one retry with feedback); every role gets at least one bullet; keywords absent from the JD are dropped. Resume text is therefore verbatim from the profile.
* **Technical Skills**: Leads with a "Relevant to this role" row of JD keywords matched by `skills_inventory` or by skill tags on the kept bullets.
* **Cover letter (LLM prose)**: Built from verified facts only; numbers absent from facts/JD, `[placeholders]`, >400 words, or >1 page are rejected (one retry).

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
│   ├── resume.typ              # Single-column ATS template; page budget enforced by fitting
│   └── cover_letter.typ        # 1-page Typst cover letter template
└── cli_tailor.py            # Subcommands: `job-butler tailor`
```

## 4. TDD Red-Phase Test Specification
Tests in `tests/unit/test_slice3_tailor.py`:

1. `test_page_budget_selection_domestic_vs_international()`:
   - For a Tier 1 (domestic) role, asserts template selects 1-page layout; for a Tier 2–4 role, asserts 2-page layout.
2. `test_mandatory_roles_included()`:
   - Uses a fixture profile; verifies every `work_experience` entry is present in all generated resumes.
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
