"""Input adapter for LinkedIn search configuration.

This module owns YAML-specific parsing and validation. The extraction core should
consume SearchDefinition objects and remain independent from YAML storage.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_DATE_POSTED = {"past_24_hours"}
MIN_KEYWORDS_LENGTH = 2


class SearchConfigError(ValueError):
    """Raised when the search configuration cannot be safely executed."""


@dataclass(frozen=True)
class SearchDefinition:
    search_id: str
    keywords: str
    location: str
    date_posted: str


def _required_text(raw: dict[str, Any], field: str, search_label: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SearchConfigError(f"{search_label}: missing or empty '{field}'.")
    return value.strip()


def validate_search(raw: Any, seen_ids: set[str], index: int) -> SearchDefinition:
    if not isinstance(raw, dict):
        raise SearchConfigError(f"Search #{index}: expected a mapping/object.")

    label = f"Search #{index}"
    search_id = _required_text(raw, "search_id", label)

    if search_id in seen_ids:
        raise SearchConfigError(f"{search_id}: duplicate search_id.")

    keywords = _required_text(raw, "keywords", search_id)
    if len(keywords) < MIN_KEYWORDS_LENGTH:
        raise SearchConfigError(
            f"{search_id}: keywords are too short to define a meaningful search."
        )

    location = _required_text(raw, "location", search_id)
    date_posted = _required_text(raw, "date_posted", search_id)

    if date_posted not in SUPPORTED_DATE_POSTED:
        supported = ", ".join(sorted(SUPPORTED_DATE_POSTED))
        raise SearchConfigError(
            f"{search_id}: unsupported date_posted '{date_posted}'. "
            f"Supported values: {supported}."
        )

    seen_ids.add(search_id)
    return SearchDefinition(
        search_id=search_id,
        keywords=keywords,
        location=location,
        date_posted=date_posted,
    )


def load_searches(path: str | Path) -> list[SearchDefinition]:
    """Load and validate all configured searches from a YAML adapter file."""
    config_path = Path(path)

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise SearchConfigError(f"Configuration file not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise SearchConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(document, dict):
        raise SearchConfigError("Configuration root must be a mapping/object.")

    if document.get("version") != 1:
        raise SearchConfigError("Unsupported or missing configuration version. Expected 1.")

    raw_searches = document.get("searches")
    if not isinstance(raw_searches, list) or not raw_searches:
        raise SearchConfigError("'searches' must contain at least one configured search.")

    searches: list[SearchDefinition] = []
    seen_ids: set[str] = set()

    # Validate independently so one bad search can be reported without changing
    # the contract consumed by the extraction core. Runtime orchestration will
    # later decide how to continue with other searches after an ERROR.
    for index, raw in enumerate(raw_searches, start=1):
        searches.append(validate_search(raw, seen_ids, index))

    return searches
