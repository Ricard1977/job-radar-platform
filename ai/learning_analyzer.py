"""Learning V1.1 analyzer.

Learns professional concepts from explicit human feedback without turning generic
words (e.g. engineer, manager, IT) into dangerous rejection rules. Patterns are
reviewable only: this module never deletes jobs and never changes Gemini scoring.
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
    "de","del","la","el","los","las","un","una","y","o","en","para","por","con","sin",
    "role","roles","puesto","puestos","perfil","position","job","relevant","work","experience"
}
# Generic terms are context, never standalone negative preferences.
BLOCKED_STANDALONE = {
    "it","ingeniero","ingeniera","ingeniero/a","engineer","engineering","manager","director",
    "jefe","jefa","jefe/a","responsable","lead","senior","project","proyectos","proyecto"
}
# Concept families. A signal contributes at most once to each family.
FAMILIES = {
    "SAP funcional / técnico": {"sap","s4hana","s/4hana","hana","fico","fi/co","basis","hcm"},
    "Cloud / IT puramente informático": {"cloud","genesys","saas","aws","azure","gcp"},
    "Software / desarrollo": {"software","developer","development","programador","programacion"},
    "Jefe/a de Obra / construcción": {"jefe de obra","jefe/a de obra","construction manager","site manager"},
    "Telecomunicaciones": {"telecomunicacion","telecomunicaciones","telecommunications"},
    "Ingeniería de Procesos": {"ingeniero de procesos","ingeniero/a de procesos","process engineer","process engineering"},
}


def confidence(n):
    return "high" if n >= 7 else "medium" if n >= 3 else "low"


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def tokenize(text):
    words = re.findall(r"[a-z0-9áéíóúüñ/+#.-]+", normalize(text))
    return [w.strip(".-") for w in words if len(w.strip(".-")) >= 2 and w not in STOPWORDS]


def family_match(text, vocabulary):
    text = normalize(text)
    ts = set(tokenize(text))
    for term in vocabulary:
        term_n = normalize(term)
        if " " in term_n:
            if term_n in text:
                return True
        elif term_n in ts:
            return True
    return False


def summarize(signals):
    counts = Counter(x.get("signal_type") for x in signals)
    return {"sample_size":len(signals),"rejected":counts.get("REJECTED",0),
            "interested":counts.get("INTERESTED",0),"applied":counts.get("APPLIED",0)}


def _pattern(name, evidence):
    unique = {int(x["id"]):x for x in evidence if x.get("id") is not None}
    rows = list(unique.values())
    return {"pattern":name,"evidence_count":len(rows),"confidence":confidence(len(rows)),
            "signal_ids":sorted(unique),
            "example_reasons":list(dict.fromkeys(x.get("reason") for x in rows if x.get("reason")))[:6],
            "example_jobs":list(dict.fromkeys(x.get("job_title") for x in rows if x.get("job_title")))[:6]}


def analyse(signals):
    counts = summarize(signals)
    rejected = [x for x in signals if x.get("signal_type")=="REJECTED"]
    positive = [x for x in signals if x.get("signal_type") in {"INTERESTED","APPLIED"}]
    family_hits, reason_hits, positive_hits = defaultdict(list), defaultdict(list), defaultdict(list)

    for row in rejected:
        # Explicit reason has priority; title is used as supporting context.
        reason = normalize(row.get("reason"))
        context = " ".join(filter(None,[reason, normalize(row.get("job_title"))]))
        for family,vocabulary in FAMILIES.items():
            if family_match(context,vocabulary):
                family_hits[family].append(row)
        # Free-text fallback only for repeated, specific user wording.
        for token in set(tokenize(reason)):
            if token not in BLOCKED_STANDALONE:
                reason_hits[token].append(row)

    for row in positive:
        for token in set(tokenize(row.get("job_title"))):
            if token not in BLOCKED_STANDALONE:
                positive_hits[token].append(row)

    candidates=[]
    family_signal_ids=set()
    for family,rows in family_hits.items():
        p=_pattern(family,rows)
        candidates.append(p)
        family_signal_ids.update(p["signal_ids"])

    # Avoid duplicate patterns such as 'obra' + 'jefe/a': if the same signals are
    # already explained by a professional family, do not promote their loose tokens.
    for token,rows in reason_hits.items():
        p=_pattern(token,rows)
        if p["evidence_count"] < 2:
            continue
        if set(p["signal_ids"]).issubset(family_signal_ids):
            continue
        candidates.append(p)

    ranked=sorted({p["pattern"]:p for p in candidates}.values(),
                  key=lambda p:(p["evidence_count"],p["pattern"]),reverse=True)
    negative=[p for p in ranked if p["confidence"] in {"medium","high"}]
    uncertain=[p for p in ranked if p["confidence"]=="low"]

    positive_patterns=[]
    for token,rows in positive_hits.items():
        p=_pattern(token,rows)
        if p["evidence_count"]>=2:
            positive_patterns.append(p)
    positive_patterns.sort(key=lambda p:p["evidence_count"],reverse=True)

    recommendations=[{"action":"REVIEW_FOR_BULK_REJECTION","pattern":p["pattern"],
                      "confidence":p["confidence"],"evidence_count":p["evidence_count"],
                      "automatic":False} for p in negative]
    text=(f"Learning V1.1: {counts['sample_size']} señales; {counts['rejected']} descartes, "
          f"{counts['interested']} intereses y {counts['applied']} aplicaciones. "
          f"{len(negative)} patrones profesionales negativos tienen evidencia suficiente para revisión.")
    return {"profile_version":2,"sample_size":counts["sample_size"],
            "positive_patterns":positive_patterns[:15],"negative_patterns":negative[:15],
            "uncertain_patterns":uncertain[:15],"scoring_recommendations":recommendations[:15],"summary":text}


def _request(method,path,body=None,prefer=None):
    base=os.environ["SUPABASE_URL"].rstrip("/")
    key=os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key: raise RuntimeError("Set SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY)")
    headers={"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    if prefer: headers["Prefer"]=prefer
    data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    req=urllib.request.Request(base+"/rest/v1/"+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=60) as response:
            raw=response.read().decode(); return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode(errors="replace")
        raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:1000]}") from exc


def run():
    fields="id,user_id,signal_type,reason,job_title,company_name,location,workplace_type,created_at"
    signals=_request("GET","learning_signals?select="+urllib.parse.quote(fields,safe=",")) or []
    grouped=defaultdict(list)
    for row in signals: grouped[row["user_id"]].append(row)
    generated=datetime.now(timezone.utc).isoformat(); profiles=[]
    for user_id,rows in grouped.items():
        profile=analyse(rows); profile.update({"user_id":user_id,"generated_at":generated,"updated_at":generated}); profiles.append(profile)
    if profiles:
        _request("POST","learned_preferences?on_conflict=user_id",profiles,"resolution=merge-duplicates,return=minimal")
    print(json.dumps({"signals":len(signals),"profiles_updated":len(profiles),"profiles":profiles},ensure_ascii=False,indent=2))

if __name__=="__main__": run()
