"""Safe cleanup candidate selection for Job Radar Issue #4.

This module never mutates job data. It converts learning re-evaluation decisions into
human-review buckets so the UI can present cleanup candidates in blocks.
"""
from dataclasses import dataclass, asdict
from typing import Iterable

@dataclass(frozen=True)
class CleanupCandidate:
    job_id: int
    confidence: float
    pattern: str
    reason: str
    bucket: str

def build_cleanup_candidates(decisions: Iterable[dict], valid_job_ids: set[int], high_threshold: float = 0.90) -> dict:
    """Partition AI decisions into probable-irrelevant and doubtful buckets.

    Only ELIMINAR recommendations are candidates. Nothing is archived or removed.
    """
    probable, doubtful = [], []
    for decision in decisions:
        try:
            job_id = int(decision["job_id"])
            confidence = float(decision.get("confidence") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if job_id not in valid_job_ids or decision.get("action") != "ELIMINAR":
            continue
        bucket = "PROBABLE_IRRELEVANT" if confidence >= high_threshold else "DOUBTFUL"
        item = CleanupCandidate(
            job_id=job_id,
            confidence=confidence,
            pattern=(decision.get("pattern") or "").strip(),
            reason=(decision.get("reason") or "").strip(),
            bucket=bucket,
        )
        (probable if bucket == "PROBABLE_IRRELEVANT" else doubtful).append(asdict(item))
    probable.sort(key=lambda x: x["confidence"], reverse=True)
    doubtful.sort(key=lambda x: x["confidence"], reverse=True)
    return {
        "probable_irrelevant": probable,
        "doubtful": doubtful,
        "candidate_count": len(probable) + len(doubtful),
        "automatic_actions": 0,
    }
