"""Learning V1 analyzer.

Reads human signals from Supabase, derives conservative reviewable preference
patterns and writes one learned profile per user to learned_preferences.
It does NOT change Gemini scoring and does NOT delete jobs.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "y", "o", "en",
    "para", "por", "con", "sin", "role", "roles", "puesto", "puestos", "perfil",
    "position", "job"
}
FAMILIES = {
    "SAP / IT empresarial": {"sap", "s4hana", "s/4hana", "hana", "fico", "basis"},
    "Cloud / IT": {"cloud", "genesys", "saas", "aws", "azure", "gcp"},
    "Software / desarrollo": {"software", "developer", "development", "programador", "programacion"},
}


def confidence(n):
    return "high" if n >= 7 else "medium" if n >= 3 else "low"


def tokenize(text):
    words = re.findall(r"[a-z0-9/+#.-]+", (text or "").lower())
    return [w.strip(".-") for w in words if len(w.strip(".-")) >= 2 and w not in STOPWORDS]


def summarize(signals):
    counts = Counter(x.get("signal_type") for x in signals)
    return {"sample_size": len(signals), "rejected": counts.get("REJECTED", 0),
            "interested": counts.get("INTERESTED", 0), "applied": counts.get("APPLIED", 0)}


def _pattern(name, evidence):
    unique = {int(x["id"]): x for x in evidence if x.get("id") is not None}
    rows = list(unique.values())
    return {"pattern": name, "evidence_count": len(rows), "confidence": confidence(len(rows)),
            "signal_ids": sorted(unique),
            "example_reasons": list(dict.fromkeys(x.get("reason") for x in rows if x.get("reason")))[:6],
            "example_jobs": list(dict.fromkeys(x.get("job_title") for x in rows if x.get("job_title")))[:6]}


def analyse(signals):
    counts = summarize(signals)
    rejected = [x for x in signals if x.get("signal_type") == "REJECTED"]
    positive = [x for x in signals if x.get("signal_type") in {"INTERESTED", "APPLIED"}]
    family_hits, reason_hits, positive_hits = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in rejected:
        reason_tokens = set(tokenize(row.get("reason")))
        context = reason_tokens | set(tokenize(row.get("job_title")))
        for family, vocabulary in FAMILIES.items():
            if context & vocabulary:
                family_hits[family].append(row)
        for token in reason_tokens:
            reason_hits[token].append(row)
    for row in positive:
        for token in set(tokenize(row.get("job_title"))):
            positive_hits[token].append(row)
    candidates, covered = [], set()
    for family, rows in family_hits.items():
        candidates.append(_pattern(family, rows)); covered |= FAMILIES[family]
    for token, rows in reason_hits.items():
        if token not in covered:
            p = _pattern(token, rows)
            if p["evidence_count"] >= 2:
                candidates.append(p)
    ranked = sorted({p["pattern"]: p for p in candidates}.values(),
                    key=lambda p: (p["evidence_count"], p["pattern"]), reverse=True)
    negative = [p for p in ranked if p["confidence"] in {"medium", "high"}]
    uncertain = [p for p in ranked if p["confidence"] == "low"]
    positive_patterns = []
    for token, rows in positive_hits.items():
        p = _pattern(token, rows)
        if p["evidence_count"] >= 2:
            positive_patterns.append(p)
    positive_patterns.sort(key=lambda p: p["evidence_count"], reverse=True)
    recommendations = [{"action": "REVIEW_FOR_BULK_REJECTION", "pattern": p["pattern"],
                        "confidence": p["confidence"], "evidence_count": p["evidence_count"],
                        "automatic": False} for p in negative]
    text = (f"Learning V1: {counts['sample_size']} señales; {counts['rejected']} descartes, "
            f"{counts['interested']} intereses y {counts['applied']} aplicaciones. "
            f"{len(negative)} patrones negativos tienen evidencia suficiente para revisión.")
    return {"profile_version": 1, "sample_size": counts["sample_size"],
            "positive_patterns": positive_patterns[:15], "negative_patterns": negative[:15],
            "uncertain_patterns": uncertain[:15], "scoring_recommendations": recommendations[:15],
            "summary": text}


def _request(method, path, body=None, prefer=None):
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise RuntimeError("Set SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY)")
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(base + "/rest/v1/" + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc


def run():
    fields = "id,user_id,signal_type,reason,job_title,company_name,location,workplace_type,created_at"
    signals = _request("GET", "learning_signals?select=" + urllib.parse.quote(fields, safe=",")) or []
    grouped = defaultdict(list)
    for row in signals:
        grouped[row["user_id"]].append(row)
    generated = datetime.now(timezone.utc).isoformat()
    profiles = []
    for user_id, rows in grouped.items():
        profile = analyse(rows)
        profile.update({"user_id": user_id, "generated_at": generated, "updated_at": generated})
        profiles.append(profile)
    if profiles:
        _request("POST", "learned_preferences?on_conflict=user_id", profiles,
                 "resolution=merge-duplicates,return=minimal")
    print(json.dumps({"signals": len(signals), "profiles_updated": len(profiles),
                      "profiles": profiles}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
