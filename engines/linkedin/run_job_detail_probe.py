"""Inventory useful public fields exposed by one LinkedIn job detail page."""

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


def attr_or_none(node, attribute: str) -> str | None:
    if not node:
        return None
    value = node.get(attribute)
    return value.strip() if isinstance(value, str) and value.strip() else None


def first_text(soup, selectors: list[str]) -> str | None:
    for selector in selectors:
        value = text_or_none(soup.select_one(selector))
        if value:
            return value
    return None


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

    workplace_type = None
    workplace_patterns = [
        ("remote", r"\b(remote|remoto|en remoto)\b"),
        ("hybrid", r"\b(hybrid|híbrido|hibrido)\b"),
        ("on-site", r"\b(on-site|onsite|presencial)\b"),
    ]
    for normalized, pattern in workplace_patterns:
        if re.search(pattern, page_text, flags=re.IGNORECASE):
            workplace_type = normalized
            break

    result = {
        "job_id": JOB_ID,
        "job_url": f"https://www.linkedin.com/jobs/view/{JOB_ID}",
        "title": first_text(soup, ["h2.top-card-layout__title", "h1"]),
        "company": first_text(soup, ["a.topcard__org-name-link", ".topcard__flavor"]),
        "company_url": attr_or_none(company_link, "href"),
        "company_logo_url": (
            attr_or_none(logo_node, "data-delayed-url") or attr_or_none(logo_node, "src")
        ),
        "location": first_text(soup, ["span.topcard__flavor--bullet", ".topcard__flavor--bullet"]),
        "description": text_or_none(description_node),
        "posted_text": text_or_none(time_node),
        "posted_datetime": attr_or_none(time_node, "datetime"),
        "salary_visible": salary_match.group(0) if salary_match else None,
        "workplace_type_detected": workplace_type,
        "job_criteria": criteria,
        "public_metadata": {
            "applicant_or_status_text": first_text(
                soup,
                [
                    ".num-applicants__caption",
                    ".topcard__flavor--metadata",
                    ".posted-time-ago__text",
                ],
            ),
            "apply_url": attr_or_none(
                soup.select_one("a.apply-button, a[data-tracking-control-name*='apply']"),
                "href",
            ),
        },
        "extraction_datetime": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
