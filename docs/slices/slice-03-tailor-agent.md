# Slice 3: Resume & Cover Letter Tailor Agent

## 1. Goal & Scope
Build the intelligent document tailoring engine. Given an active job description and the candidate profile, an LLM-driven Tailor Agent extracts required ATS keywords, ranks and selects the candidate's verified atomic bullet points (guaranteeing zero hallucinations), and renders an ATS-optimized, selectable-text PDF using **Typst**, along with a customized cover letter.

## 2. Components & Architecture
```
src/
└── agents/
    └── tailor/
        ├── __init__.py
        ├── client.py        # Unified LLM provider client (Gemini / OpenAI / Anthropic)
        ├── extractor.py     # ATS keyword and requirements parser
        ├── selector.py      # Zero-hallucination atomic bullet ranker and selector
        ├── typst_engine.py  # Typst template renderer and PDF compiler
        └── prompt.py        # System instructions and output schemas (Pydantic OutputParser)
templates/
└── resume.typ               # Single-column, ATS-standard Typst resume template
```

## 3. Zero-Hallucination & ATS Enforcement
1. **Bullet ID Constraint**: The LLM prompt receives only the candidate's registered bullet IDs and text. It returns an ordered list of bullet IDs to include.
2. **Deterministic Validator**: If any returned bullet text diverges from the canonical text in `candidate_profile.yaml`, the build falls back to the exact canonical text.
3. **Typst ATS Standards**:
   - Single-column layout, standard headings (`Experience`, `Education`, `Skills`).
   - UTF-8 clean text with zero font embedding glitches.
   - 100% copy-pasteable text without nested tables or multi-column flow.

## 4. TDD Test Specification (Red Phase)
The following tests will be written in `tests/unit/test_tailor_agent.py`:

1. `test_ats_keyword_extraction()`:
   - Feeds a sample Backend Engineer JD.
   - Asserts extraction of key tech stack items (e.g. `["Python", "FastAPI", "Distributed Systems", "Kafka"]`).
2. `test_bullet_selection_zero_hallucination()`:
   - Mocks LLM response returning selected bullet IDs.
   - Asserts validator rejects unknown bullet IDs not present in `candidate_profile.yaml`.
3. `test_typst_markup_generation()`:
   - Validates that the populated Typst template contains candidate contact info, selected bullet points, and matching skills.
4. `test_typst_pdf_compilation()`:
   - Compiles a generated `.typ` file to a binary PDF.
   - Asserts the output file starts with `%PDF-` and contains extracted text matching candidate name and skills.
5. `test_cover_letter_generation()`:
   - Asserts generated cover letter addresses the company name, references matched projects, and maintains truthful claims.

## 5. Acceptance Criteria
- [ ] 100% test pass rate with `pytest tests/unit/test_tailor*`
- [ ] Typst compiler CLI invocation runs cleanly and outputs valid PDFs.
- [ ] LLM client uses mocked responses in unit tests for fast, deterministic testing.
- [ ] Output PDF verified to be single-column and selectable text.

