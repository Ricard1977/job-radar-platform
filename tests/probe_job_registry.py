"""Controlled repeatability probe for the source-independent job registry."""

import json
from pathlib import Path

from core.job_registry import JobRegistry

TEST_PATH = Path("data/job_registry_probe.json")
TEST_JOBS = [
    {"source_job_id": "4462164766", "title": "IIoT, Industry 4.0 & Industrial AI - Innovation Expert", "company": "Sanofi"},
    {"source_job_id": "4465220423", "title": "Global Automation Project Lead | Pharma | Spain", "company": "Amaris Consulting"},
    {"source_job_id": "4469738190", "title": "Data Center Systems Engineer", "company": "Schneider Electric"},
]


def run_batch(registry: JobRegistry, run_id: str) -> dict:
    registry.start_run(run_id, "linkedin", {"probe": True, "records": len(TEST_JOBS)})
    imported = 0
    known = 0
    mapped = []

    for item in TEST_JOBS:
        source_id = item["source_job_id"]
        internal_id, is_new = registry.ingest_source_job(
            "linkedin",
            source_id,
            source_url=f"https://www.linkedin.com/jobs/view/{source_id}",
            raw_data=item,
        )
        imported += int(is_new)
        known += int(not is_new)
        mapped.append({"source_job_id": source_id, "internal_job_id": internal_id, "is_new": is_new})

    registry.finish_run(
        run_id,
        "SUCCESS",
        processed=True,
        raw_records=len(TEST_JOBS),
        unique_records=len(TEST_JOBS),
        imported=imported,
        known=known,
        errors=0,
    )
    registry.save()
    return {"run_id": run_id, "imported": imported, "known": known, "mapped": mapped}


def main() -> int:
    if TEST_PATH.exists():
        TEST_PATH.unlink()

    registry = JobRegistry(TEST_PATH)
    first = run_batch(registry, "PROBE-001")
    second = run_batch(registry, "PROBE-002")

    result = {
        "first_run": first,
        "second_run": second,
        "expected": {"first_imported": 3, "second_imported": 0, "second_known": 3},
        "passed": first["imported"] == 3 and second["imported"] == 0 and second["known"] == 3,
        "registry": registry.data,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
