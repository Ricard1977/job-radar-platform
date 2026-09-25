"""Minimal public LinkedIn Jobs extraction probe.

This is deliberately a small technical probe for the first real-data gate.
It requests the public LinkedIn jobs guest endpoint and extracts only fields
visible in result cards. It does not authenticate, use cookies, or bypass
access controls.
"""

from dataclasses import asdict, dataclass
import re
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup


GUEST_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DATE_POSTED_TO_LINKEDIN = {"past_24_hours": "r86400"}


@dataclass(frozen=True)
class PublicJob:
    job_id: str
    title: str
    company: str
    location: str
    job_url: str


def _clean(value: str) -> str:
    return " ".join(value.split())


def extract_job_id(url: str) -> str | None:
    match = re.search(r"/jobs/view/(?:[^/?#]*-)?(\d+)(?:[/?#]|$)", url)
    return match.group(1) if match else None


def fetch_public_jobs(search, start: int = 0, timeout: int = 20) -> list[PublicJob]:
    """Fetch one public result page for a validated search definition."""
    try:
        time_range = DATE_POSTED_TO_LINKEDIN[search.date_posted]
    except KeyError as exc:
        raise ValueError(f"Unsupported date_posted: {search.date_posted}") from exc

    params = {
        "keywords": search.keywords,
        "location": search.location,
        "f_TPR": time_range,
        "start": start,
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0 Safari/537.36"
        )
    }

    response = requests.get(
        GUEST_SEARCH_URL,
        params=params,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    jobs: list[PublicJob] = []

    for card in soup.select("li"):
        link = card.select_one("a.base-card__full-link")
        if link is None:
            continue

        url = link.get("href", "").strip()
        job_id = extract_job_id(url)
        if not job_id:
            continue

        title_node = card.select_one("h3.base-search-card__title")
        company_node = card.select_one("h4.base-search-card__subtitle")
        location_node = card.select_one("span.job-search-card__location")

        jobs.append(
            PublicJob(
                job_id=job_id,
                title=_clean(title_node.get_text(" ", strip=True)) if title_node else "",
                company=_clean(company_node.get_text(" ", strip=True)) if company_node else "",
                location=_clean(location_node.get_text(" ", strip=True)) if location_node else "",
                job_url=url,
            )
        )

    return jobs


def jobs_as_dicts(jobs: list[PublicJob]) -> list[dict[str, str]]:
    return [asdict(job) for job in jobs]
