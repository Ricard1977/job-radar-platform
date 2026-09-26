"""Learning V1 analyzer.
Reads human learning signals and derives reviewable preference patterns.
It does not change AI scoring or delete jobs automatically.
"""
from collections import Counter


def confidence(evidence_count):
    if evidence_count >= 7:
        return "high"
    if evidence_count >= 3:
        return "medium"
    return "low"


def summarize(signals):
    counts = Counter(x.get("signal_type") for x in signals)
    return {
        "sample_size": len(signals),
        "rejected": counts.get("REJECTED", 0),
        "interested": counts.get("INTERESTED", 0),
        "applied": counts.get("APPLIED", 0),
    }
