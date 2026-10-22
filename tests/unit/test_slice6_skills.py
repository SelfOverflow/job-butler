from pathlib import Path
from typing import Any

import pytest
import yaml

from src.analytics.skills import candidate_skills, mentioned_skills
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


@pytest.fixture
def profile() -> CandidateProfile:
    raw: dict[str, Any] = interpolate(yaml.safe_load(TEMPLATE.read_text()), ENV)
    return CandidateProfile.model_validate(raw)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("We run k8s on AWS with Terraform.", {"Kubernetes", "AWS", "Terraform"}),
        ("Postgres and Redis; GoLang services.", {"PostgreSQL", "Redis", "Go"}),
        ("React Native and React.js, TypeScript.", {"React Native", "React", "TypeScript"}),
        ("Strong communication skills.", set()),
        ("Experience with Javascript, not Java.", {"JavaScript", "Java"}),
    ],
)
def test_skill_frequency_vocabulary(text: str, expected: set[str]) -> None:
    assert mentioned_skills(text) == expected


def test_go_is_not_matched_in_ordinary_prose() -> None:
    assert "Go" not in mentioned_skills("You will go the extra mile and let go of legacy code.")


def test_candidate_skills_include_inventory_parentheticals_and_tags(
    profile: CandidateProfile,
) -> None:
    raw = profile.model_dump()
    raw["skills_inventory"] = {
        "cloud": [
            {"name": "AWS (ECS, Lambda, S3)", "proficiency": "advanced", "years_of_experience": 3}
        ]
    }
    raw["work_experience"][0]["atomic_bullets"][0]["skills"] = ["Kafka", "Socket.io"]
    have = candidate_skills(CandidateProfile.model_validate(raw))
    assert {"AWS", "AWS Lambda", "Kafka"} <= have
    assert "Kubernetes" not in have
