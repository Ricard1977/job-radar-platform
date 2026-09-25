"""Read-only quality audit for the operational job registry."""

import json
from collections import Counter
from pathlib import Path

REGISTRY = Path("data/job_registry.json")
SAMPLE_SIZE = 5


def present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return bool(value)
    return True


def main() -> int:
    with REGISTRY.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    jobs = data.get("jobs", {})
    sources = data.get("job_sources", {})
    runs = data.get("runs", {})
    total = len(jobs)

    fields = [
        "title", "company", "location", "job_url", "description",
        "company_url", "company_logo_url", "posted_text", "posted_datetime",
        "salary_text", "workplace_type_detected", "job_criteria",
    ]
    coverage = {}
    for field in fields:
        count = sum(present(job.get("raw_data", {}).get(field)) for job in jobs.values())
        coverage[field] = {"present": count, "missing": total - count, "pct": round((count / total * 100), 1) if total else 0}

    status_counts = Counter(job.get("status", "UNKNOWN") for job in jobs.values())
    source_counts = Counter(item.get("source", "UNKNOWN") for item in sources.values())
    detail_errors = [
        {"internal_job_id": internal_id, "error": job.get("detail_error")}
        for internal_id, job in jobs.items() if job.get("detail_error")
    ]

    sample = []
    for internal_id in sorted(jobs)[:SAMPLE_SIZE]:
        job = jobs[internal_id]
        raw = job.get("raw_data", {})
        linked_sources = [s for s in sources.values() if s.get("internal_job_id") == internal_id]
        sample.append({
            "internal_job_id": internal_id,
            "status": job.get("status"),
            "title": raw.get("title"),
            "company": raw.get("company"),
            "location": raw.get("location"),
            "posted_text": raw.get("posted_text"),
            "description_chars": len(raw.get("description") or ""),
            "company_logo_url": raw.get("company_logo_url"),
            "job_criteria": raw.get("job_criteria"),
            "sources": [{"source": s.get("source"), "source_job_id": s.get("source_job_id"), "source_url": s.get("source_url")} for s in linked_sources],
        })

    result = {
        "summary": {
            "jobs": total,
            "source_postings": len(sources),
            "runs": len(runs),
            "next_internal_job_number": data.get("next_internal_job_number"),
            "job_statuses": dict(status_counts),
            "sources": dict(source_counts),
            "detail_errors": len(detail_errors),
        },
        "field_coverage": coverage,
        "detail_error_items": detail_errors,
        "sample": sample,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
