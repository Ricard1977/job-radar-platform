"""Build deterministic LinkedIn Jobs search URLs from validated searches."""

from urllib.parse import urlencode


LINKEDIN_JOBS_SEARCH_URL = "https://www.linkedin.com/jobs/search/"

DATE_POSTED_TO_LINKEDIN = {
    "past_24_hours": "r86400",
}


def build_search_url(search) -> str:
    """Return a LinkedIn Jobs URL for a validated SearchDefinition.

    The core receives a search object and knows nothing about YAML or other
    input storage mechanisms. LinkedIn-specific parameter translation remains
    isolated in this module.
    """
    try:
        time_range = DATE_POSTED_TO_LINKEDIN[search.date_posted]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported LinkedIn date_posted value: {search.date_posted}"
        ) from exc

    query = urlencode(
        {
            "keywords": search.keywords,
            "location": search.location,
            "f_TPR": time_range,
        }
    )
    return f"{LINKEDIN_JOBS_SEARCH_URL}?{query}"
