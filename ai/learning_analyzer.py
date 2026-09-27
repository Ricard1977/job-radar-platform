"""Learning V1.2 analyzer.
Learns professional concepts from explicit human feedback. The profile version is a
stable fingerprint of HUMAN signals: unchanged feedback => unchanged version;
changed feedback => a new version, enabling one fresh AI re-evaluation cycle.
"""
import hashlib, json, os, re, urllib.error, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

STOPWORDS={"de","del","la","el","los","las","un","una","y","o","en","para","por","con","sin","role","roles","puesto","puestos","perfil","position","job","relevant","work","experience"}
BLOCKED_STANDALONE={"it","ingeniero","ingeniera","ingeniero/a","engineer","engineering","manager","director","jefe","jefa","jefe/a","responsable","lead","senior","project","proyectos","proyecto"}
FAMILIES={
 "SAP funcional / técnico":{"sap","s4hana","s/4hana","hana","fico","fi/co","basis","hcm"},
 "Cloud / IT puramente informático":{"cloud","genesys","saas","aws","azure","gcp"},
 "Software / desarrollo":{"software","developer","development","programador","programacion"},
 "Jefe/a de Obra / construcción":{"jefe de obra","jefe/a de obra","construction manager","site manager"},
 "Telecomunicaciones":{"telecomunicacion","telecomunicaciones","telecommunications"},
 "Ingeniería de Procesos":{"ingeniero de procesos","ingeniero/a de procesos","process engineer","process engineering"}}

def confidence(n): return "high" if n>=7 else "medium" if n>=3 else "low"
def normalize(text): return re.sub(r"\s+"," ",(text or "").lower().strip())
def tokenize(text):
    words=re.findall(r"[a-z0-9áéíóúüñ/+#.-]+",normalize(text))
    return [w.strip(".-") for w in words if len(w.strip(".-"))>=2 and w not in STOPWORDS]
def family_match(text,vocabulary):
    text=normalize(text); ts=set(tokenize(text))
    return any((normalize(t) in text if " " in normalize(t) else normalize(t) in ts) for t in vocabulary)
def summarize(signals):
    c=Counter(x.get("signal_type") for x in signals)
    return {"sample_size":len(signals),"rejected":c.get("REJECTED",0),"interested":c.get("INTERESTED",0),"applied":c.get("APPLIED",0)}
def _pattern(name,evidence):
    unique={int(x["id"]):x for x in evidence if x.get("id") is not None}; rows=list(unique.values())
    return {"pattern":name,"evidence_count":len(rows),"confidence":confidence(len(rows)),"signal_ids":sorted(unique),"example_reasons":list(dict.fromkeys(x.get("reason") for x in rows if x.get("reason")))[:6],"example_jobs":list(dict.fromkeys(x.get("job_title") for x in rows if x.get("job_title")))[:6]}
def signal_version(signals):
    # Deterministic positive bigint from human signal identity/content only.
    canonical=[{"id":x.get("id"),"type":x.get("signal_type"),"reason":x.get("reason") or "","job":x.get("job_title") or "","company":x.get("company_name") or ""} for x in sorted(signals,key=lambda r:int(r.get("id") or 0))]
    digest=hashlib.sha256(json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).digest()
    return int.from_bytes(digest[:7],"big") or 1

def analyse(signals):
    counts=summarize(signals); rejected=[x for x in signals if x.get("signal_type")=="REJECTED"]; positive=[x for x in signals if x.get("signal_type") in {"INTERESTED","APPLIED"}]
    family_hits,reason_hits,positive_hits=defaultdict(list),defaultdict(list),defaultdict(list)
    for row in rejected:
        reason=normalize(row.get("reason")); context=" ".join(filter(None,[reason,normalize(row.get("job_title"))]))
        for family,vocabulary in FAMILIES.items():
            if family_match(context,vocabulary): family_hits[family].append(row)
        for token in set(tokenize(reason)):
            if token not in BLOCKED_STANDALONE: reason_hits[token].append(row)
    for row in positive:
        for token in set(tokenize(row.get("job_title"))):
            if token not in BLOCKED_STANDALONE: positive_hits[token].append(row)
    candidates=[]; family_signal_ids=set()
    for family,rows in family_hits.items():
        p=_pattern(family,rows); candidates.append(p); family_signal_ids.update(p["signal_ids"])
    for token,rows in reason_hits.items():
        p=_pattern(token,rows)
        if p["evidence_count"]<2 or set(p["signal_ids"]).issubset(family_signal_ids): continue
        candidates.append(p)
    ranked=sorted({p["pattern"]:p for p in candidates}.values(),key=lambda p:(p["evidence_count"],p["pattern"]),reverse=True)
    negative=[p for p in ranked if p["confidence"] in {"medium","high"}]; uncertain=[p for p in ranked if p["confidence"]=="low"]
    positive_patterns=[]
    for token,rows in positive_hits.items():
        p=_pattern(token,rows)
        if p["evidence_count"]>=2: positive_patterns.append(p)
    positive_patterns.sort(key=lambda p:p["evidence_count"],reverse=True)
    recommendations=[{"action":"REVIEW_FOR_BULK_REJECTION","pattern":p["pattern"],"confidence":p["confidence"],"evidence_count":p["evidence_count"],"automatic":False} for p in negative]
    text=(f"Learning V1.2: {counts['sample_size']} señales; {counts['rejected']} descartes, {counts['interested']} intereses y {counts['applied']} aplicaciones. {len(negative)} patrones profesionales negativos tienen evidencia suficiente para revisión.")
    return {"profile_version":signal_version(signals),"sample_size":counts["sample_size"],"positive_patterns":positive_patterns[:15],"negative_patterns":negative[:15],"uncertain_patterns":uncertain[:15],"scoring_recommendations":recommendations[:15],"summary":text}

def _request(method,path,body=None,prefer=None):
    base=os.environ["SUPABASE_URL"].rstrip("/"); key=os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key: raise RuntimeError("Set SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY)")
    headers={"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    if prefer: headers["Prefer"]=prefer
    data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    req=urllib.request.Request(base+"/rest/v1/"+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=60) as response:
            raw=response.read().decode(); return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc: raise RuntimeError(f"Supabase HTTP {exc.code}: {exc.read().decode(errors='replace')[:1000]}") from exc

def run():
    fields="id,user_id,signal_type,reason,job_title,company_name,location,workplace_type,created_at"
    signals=_request("GET","learning_signals?select="+urllib.parse.quote(fields,safe=",")) or []; grouped=defaultdict(list)
    for row in signals: grouped[row["user_id"]].append(row)
    generated=datetime.now(timezone.utc).isoformat(); profiles=[]
    for user_id,rows in grouped.items():
        profile=analyse(rows); profile.update({"user_id":user_id,"generated_at":generated,"updated_at":generated}); profiles.append(profile)
    if profiles: _request("POST","learned_preferences?on_conflict=user_id",profiles,"resolution=merge-duplicates,return=minimal")
    print(json.dumps({"signals":len(signals),"profiles_updated":len(profiles),"profiles":profiles},ensure_ascii=False,indent=2))
if __name__=="__main__": run()
