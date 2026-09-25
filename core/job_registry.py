"""Source-independent storage for opportunities, external IDs and extractor runs."""

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path("data/job_registry.json")
VALID_JOB_STATUSES = {"NEW", "DISCARDED_AI", "DISCARDED_USER", "SELECTED", "APPLIED", "IN_PROCESS", "CLOSED"}
VALID_RUN_STATUSES = {"RUNNING", "SUCCESS", "ERROR"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobRegistry:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return self._empty()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("schema_version") != 2:
            raise ValueError("Unsupported registry schema; expected version 2")
        return data

    @staticmethod
    def _empty() -> dict:
        return {"schema_version": 2, "next_internal_job_number": 1, "jobs": {}, "job_sources": {}, "runs": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")

    def _new_internal_id(self) -> str:
        number = self.data["next_internal_job_number"]
        self.data["next_internal_job_number"] += 1
        return f"JR-{number:06d}"

    @staticmethod
    def source_key(source: str, source_job_id: str) -> str:
        return f"{source}:{source_job_id}"

    def find_by_source(self, source: str, source_job_id: str) -> dict | None:
        return self.data["job_sources"].get(self.source_key(source, source_job_id))

    def ingest_source_job(self, source: str, source_job_id: str, source_url: str | None = None, raw_data: dict | None = None) -> tuple[str, bool]:
        """Register an external posting. Returns (internal_job_id, is_new_source_posting)."""
        key = self.source_key(source, str(source_job_id))
        now = utcnow()
        existing = self.data["job_sources"].get(key)
        if existing:
            existing["last_seen_at"] = now
            existing["seen_count"] = existing.get("seen_count", 1) + 1
            return existing["internal_job_id"], False

        internal_id = self._new_internal_id()
        self.data["jobs"][internal_id] = {
            "internal_job_id": internal_id,
            "status": "NEW",
            "status_reason": None,
            "created_at": now,
            "updated_at": now,
            "raw_data": raw_data or {},
        }
        self.data["job_sources"][key] = {
            "internal_job_id": internal_id,
            "source": source,
            "source_job_id": str(source_job_id),
            "source_url": source_url,
            "first_seen_at": now,
            "last_seen_at": now,
            "seen_count": 1,
        }
        return internal_id, True

    def link_source(self, internal_job_id: str, source: str, source_job_id: str, source_url: str | None = None) -> None:
        """Link another external posting to an already known opportunity."""
        if internal_job_id not in self.data["jobs"]:
            raise KeyError(f"Unknown internal job: {internal_job_id}")
        key = self.source_key(source, str(source_job_id))
        if key in self.data["job_sources"]:
            return
        now = utcnow()
        self.data["job_sources"][key] = {
            "internal_job_id": internal_job_id,
            "source": source,
            "source_job_id": str(source_job_id),
            "source_url": source_url,
            "first_seen_at": now,
            "last_seen_at": now,
            "seen_count": 1,
        }

    def set_job_status(self, internal_job_id: str, status: str, reason: str | None = None, purge_payload: bool = False) -> None:
        if status not in VALID_JOB_STATUSES:
            raise ValueError(f"Invalid job status: {status}")
        job = self.data["jobs"].get(internal_job_id)
        if job is None:
            raise KeyError(f"Unknown internal job: {internal_job_id}")
        job["status"] = status
        job["status_reason"] = reason
        job["updated_at"] = utcnow()
        if purge_payload:
            job["raw_data"] = {}

    def start_run(self, run_id: str, source: str, search: dict) -> None:
        self.data["runs"][run_id] = {
            "run_id": run_id,
            "source": source,
            "search": search,
            "started_at": utcnow(),
            "finished_at": None,
            "status": "RUNNING",
            "processed": False,
            "raw_file": None,
            "raw_records": 0,
            "unique_records": 0,
            "imported": 0,
            "known": 0,
            "errors": 0,
            "error_description": None,
        }

    def finish_run(self, run_id: str, status: str, *, processed: bool, raw_file: str | None = None, raw_records: int = 0, unique_records: int = 0, imported: int = 0, known: int = 0, errors: int = 0, error_description: str | None = None) -> None:
        if status not in VALID_RUN_STATUSES - {"RUNNING"}:
            raise ValueError(f"Invalid final run status: {status}")
        run = self.data["runs"].get(run_id)
        if run is None:
            raise KeyError(f"Unknown run: {run_id}")
        run.update({
            "finished_at": utcnow(),
            "status": status,
            "processed": processed,
            "raw_file": raw_file,
            "raw_records": raw_records,
            "unique_records": unique_records,
            "imported": imported,
            "known": known,
            "errors": errors,
            "error_description": error_description,
        })
