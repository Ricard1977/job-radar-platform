"""Probe real LinkedIn public-data pagination behavior."""

import json
from pathlib import Path
import sys

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

from core.public_extractor import fetch_public_jobs, jobs_as_dicts
from input.search_config import load_searches


CONFIG_PATH = ENGINE_DIR / "config" / "searches.yaml"
PROBE_STARTS = (0, 10, 20, 30, 40)


def main() -> int:
    searches = load_searches(CONFIG_PATH)
    overall_error = False

    for search in searches:
        all_jobs = []
        pages = []

        try:
            for start in PROBE_STARTS:
                jobs = fetch_public_jobs(search, start=start)
                pages.append(
                    {
                        "start": start,
                        "records_returned": len(jobs),
                        "job_ids": [job.job_id for job in jobs],
                    }
                )
                all_jobs.extend(jobs)

            unique_by_id = {job.job_id: job for job in all_jobs}
            duplicate_count = len(all_jobs) - len(unique_by_id)

            if not all_jobs:
                overall_error = True
                status = "ERROR"
                description = "LinkedIn returned no parseable public job cards."
            else:
                status = "SUCCESS"
                description = "Pagination probe completed."

            print(
                json.dumps(
                    {
                        "search_id": search.search_id,
                        "status": status,
                        "description": description,
                        "probe_starts": list(PROBE_STARTS),
                        "records_received_total": len(all_jobs),
                        "unique_job_ids": len(unique_by_id),
                        "duplicates_across_pages": duplicate_count,
                        "pages": pages,
                        "sample_unique": jobs_as_dicts(list(unique_by_id.values())[:10]),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        except Exception as exc:
            overall_error = True
            print(
                json.dumps(
                    {
                        "search_id": search.search_id,
                        "status": "ERROR",
                        "description": f"{type(exc).__name__}: {exc}",
                        "records_extracted": len(all_jobs),
                        "pages_completed": pages,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )

    return 1 if overall_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
