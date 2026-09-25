"""Source-independent registry for known job IDs and human/AI workflow state."""

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path("data/job_registry.json")
VALID_STATUSES = {
    "NEW",
    "DISCARDED_AI",
    "DISCARDED_USER",
    "SELECTED",
    "APPLIED",
    "IN_PROCESS",
    "CLOSED",
}


class JobRegistry:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 1, "jobs": {}}
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")

    def contains(self, source: str, job_id: str) -> bool:
        return self._key(source, job_id) in self.data["jobs"]

    def get(self, source: str, job_id: str) -> dict | None:
        return self.data["jobs"].get(self._key(source, job_id))

    def register(self, source: str, job_id: str, status: str = "NEW", **metadata) -> dict:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid job status: {status}")

        key = self._key(source, job_id)
        now = datetime.now(timezone.utc).isoformat()
        existing = self.data["jobs"].get(key)

        if existing:
            existing["last_seen_at"] = now
            existing["seen_count"] = existing.get("seen_count", 1) + 1
            existing.update({k: v for k, v in metadata.items() if v is not None})
            return existing

        record = {
            "source": source,
            "job_id": str(job_id),
            "status": status,
            "status_reason": None,
            "first_seen_at": now,
            "last_seen_at": now,
            "seen_count": 1,
        }
        record.update({k: v for k, v in metadata.items() if v is not None})
        self.data["jobs"][key] = record
        return record

    def set_status(self, source: str, job_id: str, status: str, reason: str | None = None) -> dict:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid job status: {status}")
        record = self.get(source, job_id)
        if record is None:
            raise KeyError(f"Unknown job: {source}:{job_id}")
        record["status"] = status
        record["status_reason"] = reason
        record["status_updated_at"] = datetime.now(timezone.utc).isoformat()
        return record

    @staticmethod
    def _key(source: str, job_id: str) -> str:
        return f"{source}:{job_id}"
