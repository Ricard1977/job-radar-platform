"""Execute the first real LinkedIn public-data extraction probe."""

import json
from pathlib import Path
import sys

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

from core.public_extractor import fetch_public_jobs, jobs_as_dicts
from input.search_config import load_searches


CONFIG_PATH = ENGINE_DIR / "config" / "searches.yaml"


def main() -> int:
    searches = load_searches(CONFIG_PATH)
    overall_error = False

    for search in searches:
        try:
            jobs = fetch_public_jobs(search)
            if not jobs:
                overall_error = True
                print(
                    json.dumps(
                        {
                            "search_id": search.search_id,
                            "status": "ERROR",
                            "description": "LinkedIn returned no parseable public job cards.",
                            "records_extracted": 0,
                        },
                        ensure_ascii=False,
                    )
                )
                continue

            print(
                json.dumps(
                    {
                        "search_id": search.search_id,
                        "status": "SUCCESS",
                        "records_extracted": len(jobs),
                        "sample": jobs_as_dicts(jobs[:5]),
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
                        "records_extracted": 0,
                    },
                    ensure_ascii=False,
                )
            )

    return 1 if overall_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
