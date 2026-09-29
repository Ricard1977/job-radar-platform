"""Asynchronous Job Radar evaluator: persistent Work Orders -> Gemini -> ai_evaluations."""
import json, os, sys, time, random, re, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from db.database import DB_PATH, connect
from ai.work_orders import create_evaluation_order, recover_stale_processing, claim_next, mark_completed, mark_retry, mark_failed
PROFILE_PATH=ROOT/'config'/'candidate_profile_v0.yaml'; CRITERIA_PATH=ROOT/'config'/'evaluation_criteria_v0.yaml'
MODEL=os.getenv('JOB_RADAR_AI_MODEL','gemini-3.5-flash-lite'); PROFILE_VERSION='0'; CRITERIA_VERSION='0'
EVALUATOR_VERSION=f'gemini:{MODEL}:profile-{PROFILE_VERSION}_criteria-{CRITERIA_VERSION}:candidate-es-v2'
BATCH_LIMIT=int(os.getenv('JOB_RADAR_AI_LIMIT','25'))
MAX_RETRIES=int(os.getenv('JOB_RADAR_AI_MAX_RETRIES','2'))
BASE_BACKOFF=float(os.getenv('JOB_RADAR_AI_BASE_BACKOFF','2'))
INTER_JOB_DELAY=float(os.getenv('JOB_RADAR_AI_INTER_JOB_DELAY','1.0'))
QUEUE_RETRY_DELAY=int(os.getenv('JOB_RADAR_AI_QUEUE_RETRY_DELAY','300'))
MAX_ITEM_ATTEMPTS=int(os.getenv('JOB_RADAR_AI_MAX_ITEM_ATTEMPTS','8'))
TRANSIENT_HTTP={429,500,502,503,504}
SCORE_KEYS=['score','responsibility_and_seniority','project_program_delivery','engineering_technical_environment','leadership_and_stakeholders','sector_domain_transferability','critical_infrastructure_availability']
LIST_KEYS=['strongest_matches','gaps_or_risks','hard_barriers','evidence_from_job']; REQUIRED=SCORE_KEYS+['decision','short_reason']+LIST_KEYS
class GeminiHTTPError(RuntimeError):
 def __init__(self,status,message):
  super().__init__(message); self.status=status
def now(): return datetime.now(timezone.utc).isoformat()
def load_yaml(path): return yaml.safe_load(path.read_text(encoding='utf-8'))
def compact_job(row): return {'public_id':row['public_id'],'title':row['title'],'company':row['company'],'location':row['location'],'workplace_type':row['workplace_type'],'salary_text':row['salary_text'],'description':row['description']}
def as_list(v):
 if v is None:return []
 if isinstance(v,list):return v
 if isinstance(v,dict):return [f'{k}: {x}' for k,x in v.items()]
 return [str(v)]
def validate(ev):
 for k in REQUIRED:
  if k not in ev: raise ValueError(f'Missing Gemini field: {k}')
 ev['decision']=str(ev['decision']).upper().strip()
 if ev['decision'] not in {'HIGH_INTEREST','INTERESTING','REVIEW','LOW_INTEREST'}:raise ValueError('Invalid decision')
 for k in SCORE_KEYS:ev[k]=max(0,min(100,float(ev[k])))
 for k in LIST_KEYS:ev[k]=as_list(ev[k])
 ev['short_reason']=str(ev['short_reason']).strip(); return ev
def extract_json(text):
 text=text.strip()
 if text.startswith('```'):
  text=text.split('\n',1)[1] if '\n' in text else text
  if text.endswith('```'):text=text[:-3]
 try:return json.loads(text.strip())
 except json.JSONDecodeError:
  s=text.find('{');e=text.rfind('}');return json.loads(text[s:e+1])
def evaluate(api_key,profile,criteria,row):
 prompt='''Eres el evaluador de un radar laboral. Evalúa el encaje entre la oferta y el candidato, pero no decidas por él. Sigue exactamente el perfil y los criterios. Lee la descripción completa, no solo el título. Distingue falta de evidencia de incompatibilidad y no inventes datos. La descripción de la oferta NO debe traducirse ni resumirse: ya se conserva literalmente desde la fuente. IMPORTANTE: cualquier texto que TÚ generes sobre el candidato, su experiencia o su encaje con la oferta debe estar SIEMPRE en castellano, aunque la oferta esté en otro idioma. Esto incluye short_reason, strongest_matches, gaps_or_risks, hard_barriers y evidence_from_job. short_reason debe ser un comentario breve y útil sobre por qué la oferta encaja o no con el candidato. Devuelve solo el JSON solicitado.\n\nINPUT:\n'''+json.dumps({'candidate_profile':profile,'evaluation_criteria':criteria,'job':compact_job(row)},ensure_ascii=False)
 schema={'type':'OBJECT','properties':{'score':{'type':'NUMBER'},'decision':{'type':'STRING','enum':['HIGH_INTEREST','INTERESTING','REVIEW','LOW_INTEREST']},'responsibility_and_seniority':{'type':'NUMBER'},'project_program_delivery':{'type':'NUMBER'},'engineering_technical_environment':{'type':'NUMBER'},'leadership_and_stakeholders':{'type':'NUMBER'},'sector_domain_transferability':{'type':'NUMBER'},'critical_infrastructure_availability':{'type':'NUMBER'},'short_reason':{'type':'STRING'},'strongest_matches':{'type':'ARRAY','items':{'type':'STRING'}},'gaps_or_risks':{'type':'ARRAY','items':{'type':'STRING'}},'hard_barriers':{'type':'ARRAY','items':{'type':'STRING'}},'evidence_from_job':{'type':'ARRAY','items':{'type':'STRING'}}},'required':REQUIRED}
 body={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseMimeType':'application/json','responseJsonSchema':schema,'temperature':0.1}}
 url=f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(MODEL,safe='')}:generateContent?key={urllib.parse.quote(api_key,safe='')}"
 last_error=None
 for attempt in range(MAX_RETRIES+1):
  req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
  try:
   with urllib.request.urlopen(req,timeout=90) as resp:result=json.loads(resp.read().decode())
   break
  except urllib.error.HTTPError as exc:
   payload=exc.read().decode(errors='replace')[:800];last_error=GeminiHTTPError(exc.code,f"Gemini HTTP {exc.code}: {payload}")
   if exc.code not in TRANSIENT_HTTP or attempt>=MAX_RETRIES:raise last_error from exc
   delay=min(20,BASE_BACKOFF*(2**attempt))+random.uniform(0,1.5)
   print(f"Transient Gemini HTTP {exc.code} for {row['public_id']}; local retry {attempt+1}/{MAX_RETRIES} in {delay:.1f}s",file=sys.stderr,flush=True);time.sleep(delay)
  except (urllib.error.URLError,TimeoutError) as exc:
   last_error=RuntimeError(f"Gemini network error: {exc}")
   if attempt>=MAX_RETRIES:raise last_error from exc
   delay=min(20,BASE_BACKOFF*(2**attempt))+random.uniform(0,1.5);time.sleep(delay)
 else:raise last_error or RuntimeError('Gemini request failed')
 candidates=result.get('candidates') or []
 if not candidates:raise RuntimeError('Gemini returned no candidate')
 text=''.join(p.get('text','') for p in candidates[0].get('content',{}).get('parts',[])).strip();return validate(extract_json(text))
def load_job(job_id):
 with connect(DB_PATH) as conn:
  return conn.execute("SELECT j.*,c.name company FROM jobs j LEFT JOIN companies c ON c.id=j.company_id WHERE j.id=?",(job_id,)).fetchone()
def store_evaluation(row,ev):
 ts=now();detail={'short_reason':ev['short_reason'],'evidence_from_job':ev['evidence_from_job'],'profile_version':PROFILE_VERSION,'criteria_version':CRITERIA_VERSION,'provider':'google-gemini','api_model':MODEL}
 with connect(DB_PATH) as conn:
  existing=conn.execute("SELECT id FROM ai_evaluations WHERE job_id=? AND model_version=?",(row['id'],EVALUATOR_VERSION)).fetchone()
  if existing:return
  conn.execute('''INSERT INTO ai_evaluations(job_id,evaluated_at,model_version,decision,score,profile_match,technical_match,management_match,sector_match,seniority_match,strengths,weaknesses,reasoning,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(row['id'],ts,EVALUATOR_VERSION,ev['decision'],ev['score'],ev['project_program_delivery'],ev['engineering_technical_environment'],ev['leadership_and_stakeholders'],ev['sector_domain_transferability'],ev['responsibility_and_seniority'],json.dumps(ev['strongest_matches'],ensure_ascii=False),json.dumps({'gaps_or_risks':ev['gaps_or_risks'],'hard_barriers':ev['hard_barriers'],'critical_infrastructure_availability':ev['critical_infrastructure_availability']},ensure_ascii=False),json.dumps(detail,ensure_ascii=False),ts))
def main():
 api_key=os.getenv('GEMINI_API_KEY')
 if not api_key:raise RuntimeError('GEMINI_API_KEY is not configured')
 profile=load_yaml(PROFILE_PATH);criteria=load_yaml(CRITERIA_PATH)
 recovered=recover_stale_processing(EVALUATOR_VERSION)
 order=create_evaluation_order(EVALUATOR_VERSION,BATCH_LIMIT)
 print(f"WORK_ORDER created={order or 'none'} recovered_stale={recovered}",flush=True)
 processed=completed=retried=failed=0
 while processed<BATCH_LIMIT:
  item=claim_next(EVALUATOR_VERSION)
  if not item:break
  processed+=1; row=load_job(item['job_id'])
  if not row:
   mark_failed(item['id'],'Job no longer exists');failed+=1;continue
  try:
   ev=evaluate(api_key,profile,criteria,row);store_evaluation(row,ev);mark_completed(item['id']);completed+=1
  except GeminiHTTPError as exc:
   if exc.status in TRANSIENT_HTTP and item['attempts']+1<MAX_ITEM_ATTEMPTS:
    mark_retry(item['id'],exc,exc.status,QUEUE_RETRY_DELAY);retried+=1
   else:
    mark_failed(item['id'],exc,exc.status);failed+=1
  except (urllib.error.URLError,TimeoutError,RuntimeError) as exc:
   if item['attempts']+1<MAX_ITEM_ATTEMPTS:
    mark_retry(item['id'],exc,None,QUEUE_RETRY_DELAY);retried+=1
   else:
    mark_failed(item['id'],exc);failed+=1
  except Exception as exc:
   mark_failed(item['id'],exc);failed+=1
  print(f"QUEUE_PROGRESS processed={processed} completed={completed} retry_wait={retried} failed={failed}",flush=True)
  time.sleep(INTER_JOB_DELAY)
 print(json.dumps({'work_order_created':order,'processed':processed,'completed':completed,'retry_wait':retried,'failed':failed},ensure_ascii=False,indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())
