"""Render a TailoredResume to PDF with Typst and fit it to its page budget."""

import io
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pypdf
import typst

from src.agents.tailor.drafter import TailoredResume
from src.ingestion.base import contains_phrase, words
from src.ingestion.scorer import skill_variants
from src.profile.exporter import format_month, skill_group_label
from src.profile.models import CandidateProfile

TEMPLATE = Path(__file__).resolve().parents[3] / "templates" / "resume.typ"


class FitError(Exception):
    pass


def resume_data(
    resume: TailoredResume, profile: CandidateProfile, keep: set[str]
) -> dict[str, Any]:
    info = profile.personal_info
    loc = info.location
    links = (info.links.linkedin, info.links.github, info.links.portfolio)
    place = ", ".join(p for p in (loc.city, loc.state, loc.country) if p)
    roles = [
        {
            "title": role.title,
            "company": role.company,
            "dates": f"{format_month(role.start_date)} - {format_month(role.end_date)}",
            "location": role.location or "",
            "bullets": [b.text for b in bullets if b.id in keep],
        }
        for role, bullets in resume.roles
    ]
    education = [
        ", ".join(filter(None, [e.degree, e.field_of_study, e.institution]))
        + (f" ({' - '.join(filter(None, [e.start_date, e.end_date]))})" if e.start_date else "")
        + (f" | GPA: {e.gpa}" if e.gpa else "")
        for e in profile.education
    ]
    return {
        "name": info.full_name,
        "contact": [info.email, info.phone, place, *(link for link in links if link)],
        "roles": roles,
        "skills": _skills(resume, profile, keep),
        "education": education,
        "certifications": [
            f"{c.name}, {c.issuer}" + (f" ({c.year})" if c.year else "")
            for c in profile.certifications
        ],
    }


def _keyword_rank(skill: str, keywords: Sequence[str]) -> int | None:
    """Index of the first JD keyword matching `skill`.

    The full skill name matches either way round ("AWS Lambda" ~ "AWS"); shorthand
    variants ("React" for "React.js") must equal the keyword, so "React Native"
    does not match "React.js".
    """
    full, *shorthands = skill_variants(skill)
    for i, keyword in enumerate(keywords):
        kw = words(keyword)
        if contains_phrase(kw, full) or contains_phrase(full, kw) or kw in shorthands:
            return i
    return None


def _skills(resume: TailoredResume, profile: CandidateProfile, keep: set[str]) -> list[Any]:
    """Skill rows: a leading row of JD-matched verified skills, then groups by match count.

    Matches come from `skills_inventory` and the tags of bullets kept on this resume.
    """
    groups = list(profile.skills_inventory.items())
    tags = [t for _, bullets in resume.roles for b in bullets if b.id in keep for t in b.skills]
    candidates: dict[str, tuple[int, str]] = {}  # casefold -> (keyword rank, first spelling)
    for name in [s.name for _, skills in groups for s in skills] + tags:
        rank = _keyword_rank(name, resume.keywords)
        taken = {r for r, _ in candidates.values()}
        if rank is not None and rank not in taken:  # One skill per keyword.
            candidates.setdefault(name.casefold(), (rank, name))
    relevant = [name for _, name in sorted(candidates.values(), key=lambda c: c[0])]

    rows: list[tuple[int, str, list[str]]] = []
    for group, skills in groups:
        names = [s.name for s in skills]
        matched = [n for n in names if n.casefold() in candidates]
        rows.append(
            (
                len(matched),
                skill_group_label(group),
                matched + [n for n in names if n not in matched],
            )
        )
    rows.sort(key=lambda row: -row[0])  # Stable: ties keep profile order.
    lead = [{"label": "Relevant to this role", "names": relevant}] if relevant else []
    return lead + [{"label": label, "names": names} for _, label, names in rows]


def render_pdf(
    resume: TailoredResume,
    profile: CandidateProfile,
    keep: Sequence[str],
    template: Path = TEMPLATE,
) -> bytes:
    data = json.dumps(resume_data(resume, profile, set(keep)))
    pdf: bytes = typst.compile(str(template), sys_inputs={"data": data})
    return pdf


def page_count(pdf: bytes) -> int:
    return len(pypdf.PdfReader(io.BytesIO(pdf)).pages)


def fit_to_budget(
    resume: TailoredResume, profile: CandidateProfile, template: Path = TEMPLATE
) -> tuple[bytes, tuple[str, ...]]:
    """Drop the lowest-ranked bullets until the PDF fits `resume.pages`.

    A role's last remaining bullet is never dropped, so every role stays listed.
    """
    keep = list(resume.ranked_ids)
    role_of = {b.id: role.id for role, bullets in resume.roles for b in bullets}
    while True:
        pdf = render_pdf(resume, profile, keep, template)
        if page_count(pdf) <= resume.pages:
            return pdf, tuple(keep)
        droppable = [i for i in keep if sum(role_of[k] == role_of[i] for k in keep) > 1]
        if not droppable:
            pages = "page" if resume.pages == 1 else "pages"
            raise FitError(f"Cannot fit one bullet per role into {resume.pages} {pages}")
        keep.remove(droppable[-1])
