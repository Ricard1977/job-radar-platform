from pathlib import Path
import sys

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from input.search_config import SearchConfigError, load_searches


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "searches.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_loads_valid_search(tmp_path):
    path = write_config(
        tmp_path,
        """version: 1
searches:
  - search_id: SEARCH_001
    keywords: Project Manager
    location: Barcelona, España
    date_posted: past_24_hours
""",
    )

    searches = load_searches(path)

    assert len(searches) == 1
    assert searches[0].search_id == "SEARCH_001"
    assert searches[0].keywords == "Project Manager"
    assert searches[0].location == "Barcelona, España"
    assert searches[0].date_posted == "past_24_hours"


def test_rejects_missing_location(tmp_path):
    path = write_config(
        tmp_path,
        """version: 1
searches:
  - search_id: SEARCH_001
    keywords: Project Manager
    date_posted: past_24_hours
""",
    )

    with pytest.raises(SearchConfigError, match="location"):
        load_searches(path)


def test_rejects_duplicate_search_id(tmp_path):
    path = write_config(
        tmp_path,
        """version: 1
searches:
  - search_id: SEARCH_001
    keywords: Project Manager
    location: Barcelona, España
    date_posted: past_24_hours
  - search_id: SEARCH_001
    keywords: Engineering Manager
    location: Barcelona, España
    date_posted: past_24_hours
""",
    )

    with pytest.raises(SearchConfigError, match="duplicate search_id"):
        load_searches(path)


def test_rejects_one_character_keywords(tmp_path):
    path = write_config(
        tmp_path,
        """version: 1
searches:
  - search_id: SEARCH_001
    keywords: P
    location: Barcelona, España
    date_posted: past_24_hours
""",
    )

    with pytest.raises(SearchConfigError, match="too short"):
        load_searches(path)


def test_rejects_unsupported_date_posted(tmp_path):
    path = write_config(
        tmp_path,
        """version: 1
searches:
  - search_id: SEARCH_001
    keywords: Project Manager
    location: Barcelona, España
    date_posted: past_month
""",
    )

    with pytest.raises(SearchConfigError, match="unsupported date_posted"):
        load_searches(path)
