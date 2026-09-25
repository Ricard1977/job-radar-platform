from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from core.search_url import build_search_url
from input.search_config import SearchDefinition


def test_builds_expected_linkedin_search_url():
    search = SearchDefinition(
        search_id="SEARCH_001",
        keywords="Project Manager",
        location="Barcelona, España",
        date_posted="past_24_hours",
    )

    url = build_search_url(search)
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "www.linkedin.com"
    assert parsed.path == "/jobs/search/"
    assert params == {
        "keywords": ["Project Manager"],
        "location": ["Barcelona, España"],
        "f_TPR": ["r86400"],
    }


def test_url_contains_no_unapproved_filters():
    search = SearchDefinition(
        search_id="SEARCH_001",
        keywords="Project Manager",
        location="Barcelona, España",
        date_posted="past_24_hours",
    )

    params = parse_qs(urlparse(build_search_url(search)).query)

    assert set(params) == {"keywords", "location", "f_TPR"}
