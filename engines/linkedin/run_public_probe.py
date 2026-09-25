"""Probe LinkedIn public-data pagination until the result stream ends."""

import json
from pathlib import Path
import sys

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

from core.public_extractor import fetch_public_jobs, jobs_as_dicts
from input.search_config import load_searches


CONFIG_PATH = ENGINE_DIR / "config" / "searches.yaml"
PAGE_STEP = 10
MAX_PAGES = 100  # Safety guard only; not a relevance/result filter.


def main() -> int:
    searches = load_searches(CONFIG_PATH)
    overall_error = False

    for search in searches:
        all_jobs = []
        pages = []
        stop_reason = None

        try:
            for page_number in range(MAX_PAGES):
                start = page_number * PAGE_STEP
                jobs = fetch_public_jobs(search, start=start)
                pages.append(
                    {
                        "start": start,
                        "records_returned": len(jobs),
                        "job_ids": [job.job_id for job in jobs],
                    }
                )

                if not jobs:
                    stop_reason = f"empty_block_at_start_{start}"
                    break

                all_jobs.extend(jobs)
            else:
                stop_reason = f"security_limit_{MAX_PAGES}_pages_reached"
                overall_error = True

            unique_by_id = {job.job_id: job for job in all_jobs}
            duplicate_count = len(all_jobs) - len(unique_by_id)

            if not all_jobs:
                overall_error = True
                status = "ERROR"
                description = "LinkedIn returned no parseable public job cards."
            elif stop_reason.startswith("security_limit_"):
                status = "ERROR"
                description = "Safety page limit reached before an empty block was found."
            else:
                status = "SUCCESS"
                description = "Automatic pagination reached an empty result block."

            print(
                json.dumps(
                    {
                        "search_id": search.search_id,
                        "status": status,
                        "description": description,
                        "page_step": PAGE_STEP,
                        "pages_requested": len(pages),
                        "stop_reason": stop_reason,
                        "records_received_total": len(all_jobs),
                        "unique_job_ids": len(unique_by_id),
                        "duplicates_across_pages": duplicate_count,
                        "pages": pages,
                        "all_unique_jobs": jobs_as_dicts(list(unique_by_id.values())),
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
