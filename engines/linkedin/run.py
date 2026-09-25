"""Production LinkedIn ingestion pipeline.

Search -> temporary RAW -> source-ID registry -> detail for new postings ->
persist registry -> delete RAW only after verified processing.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.job_registry import JobRegistry
from core.raw_batch import delete_processed_raw, read_raw_batch, write_raw_batch
from engines.linkedin.core.public_extractor import fetch_public_jobs, jobs_as_dicts
from engines.linkedin.input.search_config import load_searches

CONFIG_PATH = ENGINE_DIR / "config" / "searches.yaml"
REGISTRY_PATH = ROOT / "data" / "job_registry.json"
RAW_DIR = ROOT / "data" / "linkedin" / "raw"
MAX_RESULTS_PER_SEARCH = 1000
PAGE_SIZE = 25
EMPTY_PAGE_STOP = 2
DETAIL_DELAY_SECONDS = 1.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_all(search) -> tuple[list, bool]:
    """Collect result cards until LinkedIn stops returning data or safety cap is reached."""
    by_id = {}
    consecutive_empty = 0
    start = 0
    truncated = False

    while start < MAX_RESULTS_PER_SEARCH:
        page = fetch_public_jobs(search, start=start)
        if not page:
            consecutive_empty += 1
            if consecutive_empty >= EMPTY_PAGE_STOP:
                break
        else:
            consecutive_empty = 0
            for job in page:
                by_id[job.job_id] = job
            if len(by_id) >= MAX_RESULTS_PER_SEARCH:
                truncated = True
                break
        start += PAGE_SIZE
        time.sleep(0.5)

    return list(by_id.values())[:MAX_RESULTS_PER_SEARCH], truncated


def fetch_detail(job_id: str) -> dict:
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    description = soup.select_one("div.show-more-less-html__markup")
    company_link = soup.select_one("a.topcard__org-name-link")
    logo = soup.select_one("img.artdeco-entity-image") or soup.select_one("img")
    criteria = {}
    for item in soup.select("li.description__job-criteria-item"):
        label = item.select_one("h3.description__job-criteria-subheader")
        value = item.select_one("span.description__job-criteria-text")
        if label:
            criteria[" ".join(label.get_text(" ", strip=True).split())] = " ".join(value.get_text(" ", strip=True).split()) if value else None
    return {
        "description": " ".join(description.get_text(" ", strip=True).split()) if description else None,
        "company_url": company_link.get("href") if company_link else None,
        "company_logo_url": (logo.get("data-delayed-url") or logo.get("src")) if logo else None,
        "job_criteria": criteria,
    }


def process_search(registry: JobRegistry, search) -> dict:
    run_id = "LIN-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    raw_path = RAW_DIR / f"{run_id}.json"
    registry.start_run(run_id, "linkedin", {"search_id": search.search_id, "keywords": search.keywords, "location": search.location, "date_posted": search.date_posted})

    try:
        cards, truncated = fetch_all(search)
        unique = {job.job_id: job for job in cards}
        write_raw_batch(raw_path, {"run_id": run_id, "source": "linkedin", "created_at": utcnow(), "search_id": search.search_id, "truncated": truncated, "jobs": jobs_as_dicts(list(unique.values()))})
        batch = read_raw_batch(raw_path)
        imported = known = detail_errors = 0
        detail_error_items = []

        for raw_job in batch["jobs"]:
            source_id = raw_job["job_id"]
            if registry.find_by_source("linkedin", source_id):
                registry.ingest_source_job("linkedin", source_id, raw_job.get("job_url"), raw_job)
                known += 1
                continue

            internal_id, _ = registry.ingest_source_job("linkedin", source_id, raw_job.get("job_url"), raw_job)
            imported += 1
            try:
                detail = fetch_detail(source_id)
                registry.data["jobs"][internal_id]["raw_data"].update(detail)
                registry.data["jobs"][internal_id]["updated_at"] = utcnow()
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                registry.data["jobs"][internal_id]["detail_error"] = error_text
                detail_error_items.append({"internal_job_id": internal_id, "source_job_id": source_id, "error": error_text})
                detail_errors += 1
            time.sleep(DETAIL_DELAY_SECONDS)

        warning = "MAX_RESULTS_REACHED" if truncated else None
        registry.finish_run(run_id, "SUCCESS", processed=True, raw_file=str(raw_path), raw_records=len(cards), unique_records=len(unique), imported=imported, known=known, errors=detail_errors, error_description=json.dumps({"warning": warning, "detail_errors": detail_error_items}, ensure_ascii=False) if warning or detail_error_items else None)
        registry.save()
        delete_processed_raw(raw_path)
        return {"run_id": run_id, "search_id": search.search_id, "status": "SUCCESS", "records": len(unique), "new": imported, "known": known, "detail_errors": detail_errors, "warning": warning}
    except Exception as exc:
        registry.finish_run(run_id, "ERROR", processed=False, raw_file=str(raw_path) if raw_path.exists() else None, error_description=f"{type(exc).__name__}: {exc}")
        registry.save()
        return {"run_id": run_id, "search_id": search.search_id, "status": "ERROR", "error": f"{type(exc).__name__}: {exc}", "raw_preserved": raw_path.exists()}


def main() -> int:
    searches = load_searches(CONFIG_PATH)
    registry = JobRegistry(REGISTRY_PATH)
    results = [process_search(registry, search) for search in searches]
    registry.save()
    print(json.dumps({"executed_at": utcnow(), "results": results}, ensure_ascii=False, indent=2))
    return 1 if any(item["status"] == "ERROR" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
