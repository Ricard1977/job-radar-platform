"""Learning V1 analyzer.

Turns human signals into reviewable preference patterns. Conservative by design:
patterns need repeated evidence before they can be proposed for bulk review.
This module does NOT change Gemini scoring and does NOT delete jobs.
"""
import re
from collections import Counter, defaultdict

STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "y", "o", "en",
    "para", "por", "con", "sin", "role", "roles", "puesto", "puestos", "perfil",
    "position", "job"
}

# V1 only merges concepts that are clearly related. Broader semantic learning can come later.
FAMILIES = {
    "SAP / IT empresarial": {"sap", "s4hana", "s/4hana", "hana", "fico", "basis"},
    "Cloud / IT": {"cloud", "genesys", "saas", "aws", "azure", "gcp"},
    "Software / desarrollo": {"software", "developer", "development", "programador", "programacion"},
}


def confidence(evidence_count):
    if evidence_count >= 7:
        return "high"
    if evidence_count >= 3:
        return "medium"
    return "low"


def tokenize(text):
    words = re.findall(r"[a-z0-9/+#.-]+", (text or "").lower())
    return [w.strip(".-") for w in words if len(w.strip(".-")) >= 2 and w not in STOPWORDS]


def summarize(signals):
    counts = Counter(x.get("signal_type") for x in signals)
    return {
        "sample_size": len(signals),
        "rejected": counts.get("REJECTED", 0),
        "interested": counts.get("INTERESTED", 0),
        "applied": counts.get("APPLIED", 0),
    }


def _pattern(name, evidence):
    unique = {int(x["id"]): x for x in evidence if x.get("id") is not None}
    rows = list(unique.values())
    return {
        "pattern": name,
        "evidence_count": len(rows),
        "confidence": confidence(len(rows)),
        "signal_ids": sorted(unique),
        "example_reasons": list(dict.fromkeys(x.get("reason") for x in rows if x.get("reason")))[:6],
        "example_jobs": list(dict.fromkeys(x.get("job_title") for x in rows if x.get("job_title")))[:6],
    }


def analyse(signals):
    """Return a learned_preferences-compatible payload, without user_id/timestamps."""
    summary_counts = summarize(signals)
    rejected = [x for x in signals if x.get("signal_type") == "REJECTED"]
    positive = [x for x in signals if x.get("signal_type") in {"INTERESTED", "APPLIED"}]

    family_hits = defaultdict(list)
    reason_hits = defaultdict(list)
    positive_hits = defaultdict(list)

    for row in rejected:
        reason_tokens = set(tokenize(row.get("reason")))
        context_tokens = reason_tokens | set(tokenize(row.get("job_title")))
        for family, vocabulary in FAMILIES.items():
            if context_tokens & vocabulary:
                family_hits[family].append(row)
        # Explicit reasons are especially valuable because they were written by the user.
        for token in reason_tokens:
            reason_hits[token].append(row)

    for row in positive:
        # APPLIED is stronger evidence than INTERESTED, but V1 keeps counts transparent.
        for token in set(tokenize(row.get("job_title"))):
            positive_hits[token].append(row)

    candidates = []
    covered = set()
    for family, rows in family_hits.items():
        p = _pattern(family, rows)
        candidates.append(p)
        covered |= FAMILIES[family]

    # Preserve repeated user wording that does not belong to a predefined family.
    for token, rows in reason_hits.items():
        if token in covered:
            continue
        p = _pattern(token, rows)
        if p["evidence_count"] >= 2:
            candidates.append(p)

    # Deduplicate and rank strongest negative patterns first.
    negative_by_name = {p["pattern"]: p for p in candidates}
    ranked_negative = sorted(
        negative_by_name.values(),
        key=lambda p: (p["evidence_count"], p["pattern"]),
        reverse=True,
    )
    negative_patterns = [p for p in ranked_negative if p["confidence"] in {"medium", "high"}]
    uncertain_patterns = [p for p in ranked_negative if p["confidence"] == "low"]

    positive_patterns = []
    for token, rows in positive_hits.items():
        p = _pattern(token, rows)
        if p["evidence_count"] >= 2:
            positive_patterns.append(p)
    positive_patterns.sort(key=lambda p: p["evidence_count"], reverse=True)

    recommendations = [
        {
            "action": "REVIEW_FOR_BULK_REJECTION",
            "pattern": p["pattern"],
            "confidence": p["confidence"],
            "evidence_count": p["evidence_count"],
            "automatic": False,
        }
        for p in negative_patterns
    ]

    text = (
        f"Learning V1: {summary_counts['sample_size']} señales; "
        f"{summary_counts['rejected']} descartes, {summary_counts['interested']} intereses y "
        f"{summary_counts['applied']} aplicaciones. "
        f"{len(negative_patterns)} patrones negativos tienen evidencia suficiente para revisión."
    )
    return {
        "profile_version": 1,
        "sample_size": summary_counts["sample_size"],
        "positive_patterns": positive_patterns[:15],
        "negative_patterns": negative_patterns[:15],
        "uncertain_patterns": uncertain_patterns[:15],
        "scoring_recommendations": recommendations[:15],
        "summary": text,
    }
