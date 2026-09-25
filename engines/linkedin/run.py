"""Production LinkedIn ingestion pipeline backed by SQLite.

Search -> temporary RAW -> SQLite deduplication -> detail for new postings ->
transactional persistence -> delete RAW only after verified processing.
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

from core.raw_batch import delete_processed_raw, read_raw_batch, write_raw_batch
from db.database import DB_PATH, connect, initialize
from engines.linkedin.core.public_extractor import fetch_public_jobs, jobs_as_dicts
from engines.linkedin.input.search_config import load_searches

CONFIG_PATH = ENGINE_DIR / "config" / "searches.yaml"
RAW_DIR = ROOT / "data" / "linkedin" / "raw"
MAX_RESULTS_PER_SEARCH = 1000
PAGE_SIZE = 25
EMPTY_PAGE_STOP = 2
DETAIL_DELAY_SECONDS = 1.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_all(search) -> tuple[list, bool]:
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


def source_id(conn, code="linkedin") -> int:
    return conn.execute("SELECT id FROM sources WHERE code=?", (code,)).fetchone()["id"]


def ensure_search(conn, search, src_id: int) -> int:
    row = conn.execute("SELECT id FROM searches WHERE public_id=?", (search.search_id,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO searches(public_id,source_id,name,keywords,location,date_filter,enabled,created_at) VALUES(?,?,?,?,?,?,1,?)", (search.search_id, src_id, search.search_id, search.keywords, search.location, search.date_posted, utcnow()))
    return cur.lastrowid


def ensure_company(conn, name: str, detail: dict) -> int | None:
    if not name:
        return None
    row = conn.execute("SELECT id FROM companies WHERE name=?", (name,)).fetchone()
    if row:
        conn.execute("UPDATE companies SET linkedin_url=COALESCE(linkedin_url,?),logo_url=COALESCE(logo_url,?),updated_at=? WHERE id=?", (detail.get("company_url"), detail.get("company_logo_url"), utcnow(), row["id"]))
        return row["id"]
    cur = conn.execute("INSERT INTO companies(name,linkedin_url,logo_url,created_at,updated_at) VALUES(?,?,?,?,?)", (name, detail.get("company_url"), detail.get("company_logo_url"), utcnow(), utcnow()))
    return cur.lastrowid


def next_public_id(conn) -> str:
    row = conn.execute("SELECT MAX(CAST(SUBSTR(public_id,4) AS INTEGER)) AS n FROM jobs WHERE public_id LIKE 'JR-%'").fetchone()
    return f"JR-{(row['n'] or 0) + 1:06d}"


def process_search(search) -> dict:
    run_public_id = "LIN-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    raw_path = RAW_DIR / f"{run_public_id}.json"
    initialize(DB_PATH)
    with connect(DB_PATH) as conn:
        src_id = source_id(conn)
        search_db_id = ensure_search(conn, search, src_id)
        run_db_id = conn.execute("INSERT INTO runs(public_id,search_id,source_id,started_at,status,processed) VALUES(?,?,?,?,?,0)", (run_public_id, search_db_id, src_id, utcnow(), "RUNNING")).lastrowid

    try:
        cards, truncated = fetch_all(search)
        unique = {job.job_id: job for job in cards}
        write_raw_batch(raw_path, {"run_id": run_public_id, "source": "linkedin", "created_at": utcnow(), "search_id": search.search_id, "truncated": truncated, "jobs": jobs_as_dicts(list(unique.values()))})
        batch = read_raw_batch(raw_path)
        imported = known = detail_errors = 0
        detail_error_items = []

        with connect(DB_PATH) as conn:
            src_id = source_id(conn)
            for raw_job in batch["jobs"]:
                external_id = str(raw_job["job_id"])
                existing = conn.execute("SELECT id,job_id,seen_count FROM job_sources WHERE source_id=? AND external_job_id=?", (src_id, external_id)).fetchone()
                if existing:
                    conn.execute("UPDATE job_sources SET last_seen_at=?,seen_count=seen_count+1,active=1 WHERE id=?", (utcnow(), existing["id"]))
                    known += 1
                    continue

                detail = {}
                detail_error = None
                try:
                    detail = fetch_detail(external_id)
                except Exception as exc:
                    detail_error = f"{type(exc).__name__}: {exc}"
                    detail_errors += 1
                company_id = ensure_company(conn, raw_job.get("company"), detail)
                public_id = next_public_id(conn)
                created = utcnow()
                job_id = conn.execute("INSERT INTO jobs(public_id,company_id,title,location,description,status,status_reason,first_seen_at,updated_at) VALUES(?,?,?,?,?,'NEW',?,?,?)", (public_id, company_id, raw_job.get("title"), raw_job.get("location"), detail.get("description"), detail_error, created, created)).lastrowid
                conn.execute("INSERT INTO job_sources(job_id,source_id,external_job_id,source_url,first_seen_at,last_seen_at,seen_count,active) VALUES(?,?,?,?,?,?,1,1)", (job_id, src_id, external_id, raw_job.get("job_url"), created, created))
                conn.execute("INSERT INTO job_events(job_id,event_type,event_date,new_value,reason,actor,created_at) VALUES(?,?,?,?,?,?,?)", (job_id, "DISCOVERED", created, "NEW", f"Discovered via {search.search_id}", "linkedin-engine", created))
                imported += 1
                if detail_error:
                    detail_error_items.append({"public_id": public_id, "source_job_id": external_id, "error": detail_error})
                time.sleep(DETAIL_DELAY_SECONDS)

            warning = "MAX_RESULTS_REACHED" if truncated else None
            conn.execute("UPDATE runs SET finished_at=?,status='SUCCESS',records_found=?,unique_records=?,new_jobs=?,known_jobs=?,detail_errors=?,truncated=?,processed=1,error_description=?,raw_file=? WHERE id=?", (utcnow(), len(cards), len(unique), imported, known, detail_errors, int(truncated), json.dumps({"warning": warning, "detail_errors": detail_error_items}, ensure_ascii=False) if warning or detail_error_items else None, str(raw_path), run_db_id))

        delete_processed_raw(raw_path)
        return {"run_id": run_public_id, "search_id": search.search_id, "status": "SUCCESS", "records": len(unique), "new": imported, "known": known, "detail_errors": detail_errors, "warning": "MAX_RESULTS_REACHED" if truncated else None}
    except Exception as exc:
        with connect(DB_PATH) as conn:
            conn.execute("UPDATE runs SET finished_at=?,status='ERROR',processed=0,error_type=?,error_description=?,raw_file=? WHERE id=?", (utcnow(), type(exc).__name__, str(exc), str(raw_path) if raw_path.exists() else None, run_db_id))
        return {"run_id": run_public_id, "search_id": search.search_id, "status": "ERROR", "error": f"{type(exc).__name__}: {exc}", "raw_preserved": raw_path.exists()}


def main() -> int:
    searches = load_searches(CONFIG_PATH)
    results = [process_search(search) for search in searches]
    print(json.dumps({"executed_at": utcnow(), "database": str(DB_PATH), "results": results}, ensure_ascii=False, indent=2))
    return 1 if any(item["status"] == "ERROR" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
