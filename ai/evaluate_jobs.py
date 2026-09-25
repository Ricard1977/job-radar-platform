"""MVP autonomous evaluator: SQLite jobs -> Gemini -> ai_evaluations."""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from db.database import DB_PATH, connect

PROFILE_PATH=ROOT/'config'/'candidate_profile_v0.yaml'
CRITERIA_PATH=ROOT/'config'/'evaluation_criteria_v0.yaml'
MODEL=os.getenv('JOB_RADAR_AI_MODEL','gemini-3.5-flash-lite')
PROFILE_VERSION='0'; CRITERIA_VERSION='0'
EVALUATOR_VERSION=f'gemini:{MODEL}:profile-{PROFILE_VERSION}_criteria-{CRITERIA_VERSION}:parser-v2'
BATCH_LIMIT=int(os.getenv('JOB_RADAR_AI_LIMIT','25'))

SCORE_KEYS=['score','responsibility_and_seniority','project_program_delivery','engineering_technical_environment','leadership_and_stakeholders','sector_domain_transferability','critical_infrastructure_availability']
LIST_KEYS=['strongest_matches','gaps_or_risks','hard_barriers','evidence_from_job']
REQUIRED=SCORE_KEYS+['decision','short_reason']+LIST_KEYS

def now(): return datetime.now(timezone.utc).isoformat()
def load_yaml(path): return yaml.safe_load(path.read_text(encoding='utf-8'))
def compact_job(row):
 return {'public_id':row['public_id'],'title':row['title'],'company':row['company'],'location':row['location'],'workplace_type':row['workplace_type'],'salary_text':row['salary_text'],'description':row['description']}

def as_list(value):
 if value is None: return []
 if isinstance(value,list): return value
 if isinstance(value,dict): return [f'{k}: {v}' for k,v in value.items()]
 return [str(value)]

def validate(ev):
 if not isinstance(ev,dict): raise ValueError('Gemini output is not an object')
 for key in REQUIRED:
  if key not in ev: raise ValueError(f'Missing Gemini field: {key}')
 decision=str(ev['decision']).upper().strip()
 if decision not in {'HIGH_INTEREST','INTERESTING','REVIEW','LOW_INTEREST'}: raise ValueError('Invalid decision')
 ev['decision']=decision
 for key in SCORE_KEYS:
  ev[key]=max(0,min(100,float(ev[key])))
 for key in LIST_KEYS:
  ev[key]=as_list(ev[key])
 ev['short_reason']=str(ev['short_reason']).strip()
 return ev

def extract_json(text):
 text=text.strip()
 if text.startswith('```'):
  text=text.split('\n',1)[1] if '\n' in text else text
  if text.endswith('```'): text=text[:-3]
  text=text.strip()
 try: return json.loads(text)
 except json.JSONDecodeError:
  start=text.find('{'); end=text.rfind('}')
  if start>=0 and end>start: return json.loads(text[start:end+1])
  raise

def evaluate(api_key,profile,criteria,row):
 prompt='''You are the first-pass evaluator for a job radar. Evaluate fit, do not decide for the candidate. Follow the supplied profile and criteria exactly. Read the complete description, not just the title. Distinguish missing evidence from mismatch. Do not invent facts. Return one JSON object matching the requested schema. Keep reasons concise and evidence-based.\n\nINPUT:\n'''+json.dumps({'candidate_profile':profile,'evaluation_criteria':criteria,'job':compact_job(row)},ensure_ascii=False)
 schema={'type':'OBJECT','properties':{
  'score':{'type':'NUMBER'},'decision':{'type':'STRING','enum':['HIGH_INTEREST','INTERESTING','REVIEW','LOW_INTEREST']},
  'responsibility_and_seniority':{'type':'NUMBER'},'project_program_delivery':{'type':'NUMBER'},'engineering_technical_environment':{'type':'NUMBER'},
  'leadership_and_stakeholders':{'type':'NUMBER'},'sector_domain_transferability':{'type':'NUMBER'},'critical_infrastructure_availability':{'type':'NUMBER'},
  'short_reason':{'type':'STRING'},'strongest_matches':{'type':'ARRAY','items':{'type':'STRING'}},'gaps_or_risks':{'type':'ARRAY','items':{'type':'STRING'}},
  'hard_barriers':{'type':'ARRAY','items':{'type':'STRING'}},'evidence_from_job':{'type':'ARRAY','items':{'type':'STRING'}}},'required':REQUIRED}
 body={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseMimeType':'application/json','responseJsonSchema':schema,'temperature':0.1}}
 url=f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(MODEL,safe='')}:generateContent?key={urllib.parse.quote(api_key,safe='')}"
 req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=60) as resp: result=json.loads(resp.read().decode())
 except urllib.error.HTTPError as exc:
  detail=exc.read().decode(errors='replace'); raise RuntimeError(f'Gemini HTTP {exc.code}: {detail[:800]}') from exc
 candidates=result.get('candidates') or []
 if not candidates: raise RuntimeError(f'Gemini returned no candidate: {json.dumps(result,ensure_ascii=False)[:800]}')
 text=''.join(p.get('text','') for p in candidates[0].get('content',{}).get('parts',[])).strip()
 if not text: raise RuntimeError('Gemini returned empty text')
 return validate(extract_json(text))

def main():
 api_key=os.getenv('GEMINI_API_KEY')
 if not api_key: raise RuntimeError('GEMINI_API_KEY is not configured')
 profile=load_yaml(PROFILE_PATH); criteria=load_yaml(CRITERIA_PATH)
 with connect(DB_PATH) as conn:
  rows=conn.execute('''SELECT j.*,c.name company FROM jobs j LEFT JOIN companies c ON c.id=j.company_id WHERE NOT EXISTS (SELECT 1 FROM ai_evaluations a WHERE a.job_id=j.id AND a.model_version=?) ORDER BY j.id DESC LIMIT ?''',(EVALUATOR_VERSION,BATCH_LIMIT)).fetchall()
 total=len(rows); ok=errors=0; results=[]
 for row in rows:
  try:
   ev=evaluate(api_key,profile,criteria,row); ts=now()
   with connect(DB_PATH) as conn:
    conn.execute('''INSERT INTO ai_evaluations(job_id,evaluated_at,model_version,decision,score,profile_match,technical_match,management_match,sector_match,seniority_match,strengths,weaknesses,reasoning,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(row['id'],ts,EVALUATOR_VERSION,ev['decision'],ev['score'],ev['project_program_delivery'],ev['engineering_technical_environment'],ev['leadership_and_stakeholders'],ev['sector_domain_transferability'],ev['responsibility_and_seniority'],json.dumps(ev['strongest_matches'],ensure_ascii=False),json.dumps({'gaps_or_risks':ev['gaps_or_risks'],'hard_barriers':ev['hard_barriers'],'critical_infrastructure_availability':ev['critical_infrastructure_availability']},ensure_ascii=False),json.dumps({'short_reason':ev['short_reason'],'evidence_from_job':ev['evidence_from_job'],'profile_version':PROFILE_VERSION,'criteria_version':CRITERIA_VERSION,'provider':'google-gemini','api_model':MODEL},ensure_ascii=False),ts))
   ok+=1; results.append({'job':row['public_id'],'score':ev['score'],'decision':ev['decision'],'reason':ev['short_reason']})
  except Exception as exc:
   errors+=1; results.append({'job':row['public_id'],'error':f'{type(exc).__name__}: {exc}'})
  time.sleep(.3)
 print(json.dumps({'provider':'google-gemini','model':MODEL,'evaluator_version':EVALUATOR_VERSION,'selected':total,'evaluated':ok,'errors':errors,'results':results},ensure_ascii=False,indent=2))
 return 1 if errors else 0
if __name__=='__main__': raise SystemExit(main())
