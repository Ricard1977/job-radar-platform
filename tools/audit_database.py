"""Read-only integrity and quality audit for the operational SQLite database."""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from db.database import DB_PATH, connect


def scalar(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def main() -> int:
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)

    with connect(DB_PATH) as conn:
        tables = ["jobs", "companies", "sources", "searches", "runs", "job_sources", "ai_evaluations", "applications", "job_events"]
        counts = {table: scalar(conn, f"SELECT COUNT(*) FROM {table}") for table in tables}

        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = [dict(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]

        duplicate_public_ids = scalar(conn, "SELECT COUNT(*) FROM (SELECT public_id,COUNT(*) c FROM jobs GROUP BY public_id HAVING c>1)")
        duplicate_external_ids = scalar(conn, "SELECT COUNT(*) FROM (SELECT source_id,external_job_id,COUNT(*) c FROM job_sources GROUP BY source_id,external_job_id HAVING c>1)")
        orphan_job_sources = scalar(conn, "SELECT COUNT(*) FROM job_sources js LEFT JOIN jobs j ON j.id=js.job_id WHERE j.id IS NULL")
        jobs_without_source = scalar(conn, "SELECT COUNT(*) FROM jobs j LEFT JOIN job_sources js ON js.job_id=j.id WHERE js.id IS NULL")
        jobs_without_company = scalar(conn, "SELECT COUNT(*) FROM jobs WHERE company_id IS NULL")
        invalid_public_ids = scalar(conn, "SELECT COUNT(*) FROM jobs WHERE public_id NOT GLOB 'JR-[0-9][0-9][0-9][0-9][0-9][0-9]'")

        coverage_fields = ["title", "location", "description", "workplace_type", "salary_text"]
        coverage = {}
        total = counts["jobs"]
        for field in coverage_fields:
            present = scalar(conn, f"SELECT COUNT(*) FROM jobs WHERE {field} IS NOT NULL AND TRIM(CAST({field} AS TEXT)) <> ''")
            coverage[field] = {"present": present, "missing": total - present, "pct": round(present * 100 / total, 1) if total else 0}

        company_logo_present = scalar(conn, "SELECT COUNT(*) FROM companies WHERE logo_url IS NOT NULL AND TRIM(logo_url)<>''")
        company_linkedin_present = scalar(conn, "SELECT COUNT(*) FROM companies WHERE linkedin_url IS NOT NULL AND TRIM(linkedin_url)<>''")
        company_coverage = {
            "logo_url": {"present": company_logo_present, "missing": counts["companies"] - company_logo_present},
            "linkedin_url": {"present": company_linkedin_present, "missing": counts["companies"] - company_linkedin_present},
        }

        run_summary = [dict(row) for row in conn.execute("SELECT public_id,status,records_found,unique_records,new_jobs,known_jobs,detail_errors,truncated,processed,started_at,finished_at FROM runs ORDER BY id DESC LIMIT 10")]
        source_summary = [dict(row) for row in conn.execute("SELECT s.code,s.name,COUNT(js.id) AS postings FROM sources s LEFT JOIN job_sources js ON js.source_id=s.id GROUP BY s.id ORDER BY s.id")]
        status_summary = [dict(row) for row in conn.execute("SELECT status,COUNT(*) AS jobs FROM jobs GROUP BY status ORDER BY jobs DESC")]

        sample = [dict(row) for row in conn.execute("""
            SELECT j.public_id,j.title,c.name AS company,j.location,j.status,
                   js.external_job_id,js.source_url,js.seen_count,
                   LENGTH(COALESCE(j.description,'')) AS description_chars
            FROM jobs j
            LEFT JOIN companies c ON c.id=j.company_id
            LEFT JOIN job_sources js ON js.job_id=j.id
            ORDER BY j.id DESC LIMIT 5
        """)]

        checks = {
            "sqlite_integrity_ok": integrity == "ok",
            "foreign_key_violations": len(foreign_keys),
            "duplicate_public_ids": duplicate_public_ids,
            "duplicate_external_ids": duplicate_external_ids,
            "orphan_job_sources": orphan_job_sources,
            "jobs_without_source": jobs_without_source,
            "invalid_public_ids": invalid_public_ids,
        }
        passed = integrity == "ok" and not foreign_keys and duplicate_public_ids == 0 and duplicate_external_ids == 0 and orphan_job_sources == 0 and jobs_without_source == 0 and invalid_public_ids == 0

        result = {
            "database": str(DB_PATH),
            "passed": passed,
            "counts": counts,
            "integrity_checks": checks,
            "informational": {"jobs_without_company": jobs_without_company},
            "job_field_coverage": coverage,
            "company_field_coverage": company_coverage,
            "job_statuses": status_summary,
            "sources": source_summary,
            "recent_runs": run_summary,
            "latest_jobs_sample": sample,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
