"""Probe which useful fields are publicly available on one LinkedIn job detail page."""

import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


JOB_ID = "4465220423"
JOB_URL = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{JOB_ID}"


def clean(value: str) -> str:
    return " ".join(value.split())


def text_or_none(node) -> str | None:
    return clean(node.get_text(" ", strip=True)) if node else None


def main() -> int:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0 Safari/537.36"
        )
    }

    response = requests.get(JOB_URL, headers=headers, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    description_node = soup.select_one("div.show-more-less-html__markup")
    company_link = soup.select_one("a.topcard__org-name-link")
    logo_node = soup.select_one("img.artdeco-entity-image") or soup.select_one("img")
    time_node = soup.select_one("time")

    criteria = {}
    for item in soup.select("li.description__job-criteria-item"):
        label = text_or_none(item.select_one("h3.description__job-criteria-subheader"))
        value = text_or_none(item.select_one("span.description__job-criteria-text"))
        if label:
            criteria[label] = value

    page_text = clean(soup.get_text(" ", strip=True))
    salary_match = re.search(
        r"(?:€|EUR|USD|\$)\s?[\d.,]+(?:\s*[-–]\s*(?:€|EUR|USD|\$)?\s?[\d.,]+)?(?:\s*/\s*(?:year|month|hour|año|mes|hora))?",
        page_text,
        flags=re.IGNORECASE,
    )

    result = {
        "job_id": JOB_ID,
        "job_url": f"https://www.linkedin.com/jobs/view/{JOB_ID}",
        "description": text_or_none(description_node),
        "company_url": company_link.get("href") if company_link else None,
        "company_logo_url": logo_node.get("data-delayed-url") or logo_node.get("src") if logo_node else None,
        "posted_datetime": time_node.get("datetime") if time_node else None,
        "salary_visible": salary_match.group(0) if salary_match else None,
        "job_criteria": criteria,
        "extraction_datetime": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
