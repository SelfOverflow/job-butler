"""Render the full profile as an ATS-friendly Markdown master resume."""

import calendar

from src.profile.models import CandidateProfile


def format_month(value: str | None) -> str:
    """`2023-01` -> `Jan 2023`; None -> `Present`."""
    if value is None:
        return "Present"
    year, month = value.split("-")
    return f"{calendar.month_abbr[int(month)]} {year}"


def to_markdown(profile: CandidateProfile) -> str:
    info = profile.personal_info
    loc = info.location
    place = ", ".join(p for p in (loc.city, loc.state, loc.country) if p)
    links = (info.links.linkedin, info.links.github, info.links.portfolio)
    contact = " | ".join([info.email, info.phone, place, *(link for link in links if link)])
    lines = [f"# {info.full_name}", "", contact, "", "## Professional Experience", ""]

    for role in profile.work_experience:
        dates = f"{format_month(role.start_date)} - {format_month(role.end_date)}"
        lines += [
            f"### {role.title}, {role.company}",
            " | ".join(filter(None, [dates, role.location])),
            "",
        ]
        lines += [f"- {bullet.text}" for bullet in role.atomic_bullets] + [""]

    if profile.skills_inventory:
        lines += ["## Technical Skills", ""]
        for group, skills in profile.skills_inventory.items():
            label = group.replace("_", " ").capitalize()
            lines.append(f"- **{label}:** {', '.join(s.name for s in skills)}")
        lines.append("")

    if profile.education:
        lines += ["## Education", ""]
        for edu in profile.education:
            degree = ", ".join(filter(None, [edu.degree, edu.field_of_study]))
            entry = f"- **{degree}**, {edu.institution}"
            if edu.start_date or edu.end_date:
                entry += f" ({' - '.join(filter(None, [edu.start_date, edu.end_date]))})"
            if edu.gpa:
                entry += f" | GPA: {edu.gpa}"
            lines.append(entry)
        lines.append("")

    if profile.certifications:
        lines += ["## Certifications", ""]
        for cert in profile.certifications:
            year = f" ({cert.year})" if cert.year else ""
            lines.append(f"- {cert.name}, {cert.issuer}{year}")
        lines.append("")

    return "\n".join(lines)
