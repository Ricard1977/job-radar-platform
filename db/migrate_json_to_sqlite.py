"""One-time controlled migration from job_registry.json to relational SQLite."""

import json
from datetime import datetime, timezone
from pathlib import Path

from database import DB_PATH, connect, initialize

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data" / "job_registry.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_source_id(conn, code: str) -> int:
    row = conn.execute("SELECT id FROM sources WHERE code = ?", (code,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO sources(code,name,source_type,enabled) VALUES(?,?,?,1)", (code, code.title(), "job_board"))
    return cur.lastrowid


def get_company_id(conn, name, raw) -> int | None:
    if not name:
        return None
    row = conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()
    if row:
        conn.execute("UPDATE companies SET website=COALESCE(website,?), linkedin_url=COALESCE(linkedin_url,?), logo_url=COALESCE(logo_url,?), updated_at=? WHERE id=?", (raw.get("company_website"), raw.get("company_url"), raw.get("company_logo_url"), now(), row["id"]))
        return row["id"]
    cur = conn.execute("INSERT INTO companies(name,website,linkedin_url,logo_url,created_at,updated_at) VALUES(?,?,?,?,?,?)", (name, raw.get("company_website"), raw.get("company_url"), raw.get("company_logo_url"), now(), now()))
    return cur.lastrowid


def main() -> int:
    if not JSON_PATH.exists():
        raise FileNotFoundError(JSON_PATH)
    if DB_PATH.exists():
        DB_PATH.unlink()
    initialize(DB_PATH)
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    with connect(DB_PATH) as conn:
        internal_to_db = {}
        for public_id, record in sorted(data.get("jobs", {}).items()):
            raw = record.get("raw_data", {})
            company_id = get_company_id(conn, raw.get("company"), raw)
            cur = conn.execute("""INSERT INTO jobs(public_id,company_id,title,location,workplace_type,description,salary_text,salary_min,salary_max,salary_currency,salary_period,status,status_reason,first_seen_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                public_id, company_id, raw.get("title"), raw.get("location"), raw.get("workplace_type_detected"), raw.get("description"), raw.get("salary_text"), raw.get("salary_min"), raw.get("salary_max"), raw.get("salary_currency"), raw.get("salary_period"), record.get("status", "NEW"), record.get("status_reason"), record.get("created_at") or now(), record.get("updated_at") or now()))
            internal_to_db[public_id] = cur.lastrowid

        for item in data.get("job_sources", {}).values():
            source_id = get_source_id(conn, item.get("source", "unknown"))
            job_id = internal_to_db[item["internal_job_id"]]
            conn.execute("""INSERT INTO job_sources(job_id,source_id,external_job_id,source_url,first_seen_at,last_seen_at,seen_count,active)
                VALUES(?,?,?,?,?,?,?,1)""", (job_id, source_id, item["source_job_id"], item.get("source_url"), item.get("first_seen_at") or now(), item.get("last_seen_at") or now(), item.get("seen_count", 1)))

        # Preserve historical runs. Existing JSON did not have normalized SEARCH rows,
        # so create/reuse searches from the run search metadata.
        search_cache = {}
        for run in data.get("runs", {}).values():
            source_code = run.get("source", "unknown")
            source_id = get_source_id(conn, source_code)
            search = run.get("search") or {}
            key = (source_id, search.get("search_id"), search.get("keywords"), search.get("location"), search.get("date_posted"))
            if key not in search_cache:
                public_search_id = search.get("search_id") or f"MIGRATED-{len(search_cache)+1:03d}"
                existing = conn.execute("SELECT id FROM searches WHERE public_id=?", (public_search_id,)).fetchone()
                if existing:
                    search_cache[key] = existing["id"]
                else:
                    cur = conn.execute("INSERT INTO searches(public_id,source_id,name,keywords,location,date_filter,enabled,created_at) VALUES(?,?,?,?,?,?,1,?)", (public_search_id, source_id, public_search_id, search.get("keywords"), search.get("location"), search.get("date_posted"), run.get("started_at") or now()))
                    search_cache[key] = cur.lastrowid
            conn.execute("""INSERT INTO runs(public_id,search_id,source_id,started_at,finished_at,status,records_found,unique_records,new_jobs,known_jobs,detail_errors,truncated,processed,error_description,raw_file)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (run["run_id"], search_cache[key], source_id, run.get("started_at") or now(), run.get("finished_at"), run.get("status", "ERROR"), run.get("raw_records", 0), run.get("unique_records", 0), run.get("imported", 0), run.get("known", 0), run.get("errors", 0), 1 if "MAX_RESULTS_REACHED" in (run.get("error_description") or "") else 0, 1 if run.get("processed") else 0, run.get("error_description"), run.get("raw_file")))

        counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("jobs","companies","job_sources","sources","searches","runs")}
        orphan_sources = conn.execute("SELECT COUNT(*) FROM job_sources js LEFT JOIN jobs j ON j.id=js.job_id WHERE j.id IS NULL").fetchone()[0]
        duplicate_external = conn.execute("SELECT COUNT(*) FROM (SELECT source_id,external_job_id,COUNT(*) c FROM job_sources GROUP BY source_id,external_job_id HAVING c>1)").fetchone()[0]
        missing_public_ids = conn.execute("SELECT COUNT(*) FROM jobs WHERE public_id IS NULL OR public_id='' ").fetchone()[0]
        result = {"database": str(DB_PATH), "counts": counts, "validation": {"json_jobs": len(data.get("jobs", {})), "json_job_sources": len(data.get("job_sources", {})), "jobs_match": counts["jobs"] == len(data.get("jobs", {})), "sources_match": counts["job_sources"] == len(data.get("job_sources", {})), "orphan_job_sources": orphan_sources, "duplicate_external_ids": duplicate_external, "missing_public_ids": missing_public_ids}}
        result["passed"] = result["validation"]["jobs_match"] and result["validation"]["sources_match"] and orphan_sources == 0 and duplicate_external == 0 and missing_public_ids == 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["passed"]:
            raise RuntimeError("Migration validation failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
