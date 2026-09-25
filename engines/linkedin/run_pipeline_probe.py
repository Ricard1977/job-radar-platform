"""End-to-end probe: search -> RAW -> registry -> new IDs -> detail -> cleanup."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE_DIR))

from core.job_registry import JobRegistry
from core.raw_batch import delete_processed_raw, read_raw_batch, write_raw_batch
from engines.linkedin.core.public_extractor import fetch_public_jobs, jobs_as_dicts
from engines.linkedin.input.search_config import load_searches

CONFIG_PATH = ENGINE_DIR / "config" / "searches.yaml"
PROBE_REGISTRY = ROOT / "data" / "pipeline_probe_registry.json"
RAW_DIR = ROOT / "data" / "raw" / "linkedin"
DETAIL_LIMIT = 3  # Probe safety limit only; production pipeline will not use this cap.


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        h = item.select_one("h3.description__job-criteria-subheader")
        v = item.select_one("span.description__job-criteria-text")
        if h:
            criteria[" ".join(h.get_text(" ", strip=True).split())] = " ".join(v.get_text(" ", strip=True).split()) if v else None
    return {
        "description": " ".join(description.get_text(" ", strip=True).split()) if description else None,
        "company_url": company_link.get("href") if company_link else None,
        "company_logo_url": (logo.get("data-delayed-url") or logo.get("src")) if logo else None,
        "job_criteria": criteria,
    }


def main() -> int:
    searches = load_searches(CONFIG_PATH)
    if not searches:
        raise RuntimeError("No LinkedIn searches configured")
    search = searches[0]
    run_id = "LIN-PROBE-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = RAW_DIR / f"{run_id}.json"
    registry = JobRegistry(PROBE_REGISTRY)
    registry.start_run(run_id, "linkedin", {"search_id": search.search_id, "keywords": search.keywords, "location": search.location, "date_posted": search.date_posted})

    try:
        # Small real search page: enough to validate the orchestration without stressing LinkedIn.
        cards = fetch_public_jobs(search, start=0)
        unique = {job.job_id: job for job in cards}
        raw_payload = {"run_id": run_id, "source": "linkedin", "created_at": utcnow(), "search_id": search.search_id, "jobs": jobs_as_dicts(list(unique.values()))}
        write_raw_batch(raw_path, raw_payload)

        imported = 0
        known = 0
        detail_downloaded = 0
        detail_errors = 0
        batch = read_raw_batch(raw_path)

        for raw_job in batch["jobs"]:
            source_id = raw_job["job_id"]
            existing = registry.find_by_source("linkedin", source_id)
            if existing:
                registry.ingest_source_job("linkedin", source_id, raw_job.get("job_url"), raw_job)
                known += 1
                continue

            internal_id, _ = registry.ingest_source_job("linkedin", source_id, raw_job.get("job_url"), raw_job)
            imported += 1
            if detail_downloaded < DETAIL_LIMIT:
                try:
                    detail = fetch_detail(source_id)
                    registry.data["jobs"][internal_id]["raw_data"].update(detail)
                    registry.data["jobs"][internal_id]["updated_at"] = utcnow()
                    detail_downloaded += 1
                except Exception as exc:
                    registry.data["jobs"][internal_id]["detail_error"] = f"{type(exc).__name__}: {exc}"
                    detail_errors += 1

        registry.finish_run(run_id, "SUCCESS", processed=True, raw_file=str(raw_path), raw_records=len(cards), unique_records=len(unique), imported=imported, known=known, errors=detail_errors)
        registry.save()
        delete_processed_raw(raw_path)

        print(json.dumps({"run_id": run_id, "status": "SUCCESS", "raw_created": True, "raw_deleted_after_processing": not raw_path.exists(), "raw_records": len(cards), "unique_records": len(unique), "new": imported, "known": known, "details_downloaded": detail_downloaded, "detail_errors": detail_errors, "probe_detail_limit": DETAIL_LIMIT}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        registry.finish_run(run_id, "ERROR", processed=False, raw_file=str(raw_path) if raw_path.exists() else None, error_description=f"{type(exc).__name__}: {exc}")
        registry.save()
        print(json.dumps({"run_id": run_id, "status": "ERROR", "raw_preserved": raw_path.exists(), "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
