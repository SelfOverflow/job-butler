from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from src.ingestion.recency import RECENCY_HOURS, is_recent, search_tbs
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
TODAY = date(2026, 10, 22)
NOW = datetime(2026, 10, 22, 12, 0)


@pytest.mark.parametrize(
    ("recency", "tbs"),
    [
        ("24h", "qdr:d"),
        ("48h", "cdr:1,cd_min:10/20/2026,cd_max:10/22/2026"),
        ("72h", "cdr:1,cd_min:10/19/2026,cd_max:10/22/2026"),
        ("1w", "qdr:w"),
        ("2w", "cdr:1,cd_min:10/08/2026,cd_max:10/22/2026"),
        ("1m", "qdr:m"),
        ("any", None),
    ],
)
def test_search_tbs(recency: str, tbs: str | None) -> None:
    assert search_tbs(recency, today=TODAY) == tbs  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("posted", "recency", "recent"),
    [
        (datetime(2026, 10, 21, 13, 0), "24h", True),
        (datetime(2026, 10, 21, 11, 0), "24h", False),
        (datetime(2026, 10, 19, 13, 0), "72h", True),
        (datetime(2026, 10, 1), "1w", False),
        (datetime(2020, 1, 1), "any", True),
        (None, "24h", True),  # unknown age is kept
    ],
)
def test_is_recent(posted: datetime | None, recency: str, recent: bool) -> None:
    assert is_recent(posted, recency, now=NOW) is recent  # type: ignore[arg-type]


def test_recency_hours_cover_every_option() -> None:
    assert RECENCY_HOURS == {
        "24h": 24,
        "48h": 48,
        "72h": 72,
        "1w": 168,
        "2w": 336,
        "1m": 720,
        "any": None,
    }


def test_profile_recency_preference() -> None:
    raw: dict[str, Any] = interpolate(yaml.safe_load(TEMPLATE.read_text()), ENV)
    assert CandidateProfile.model_validate(raw).preferences.job_recency == "1w"  # default
    raw["preferences"]["job_recency"] = "72h"
    assert CandidateProfile.model_validate(raw).preferences.job_recency == "72h"
    raw["preferences"]["job_recency"] = "3 days"
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(raw)
