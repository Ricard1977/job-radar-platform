"""MVP autonomous evaluator: SQLite jobs -> Gemini -> ai_evaluations."""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from db.database import DB_PATH, connect
PROFILE_PATH=ROOT/'config'/'candidate_profile_v0.yaml'; CRITERIA_PATH=ROOT/'config'/'evaluation_criteria_v0.yaml'
MODEL=os.getenv('JOB_RADAR_AI_MODEL','gemini-3.5-flash-lite'); PROFILE_VERSION='0'; CRITERIA_VERSION='0'
EVALUATOR_VERSION=f'gemini:{MODEL}:profile-{PROFILE_VERSION}_criteria-{CRITERIA_VERSION}:candidate-es-v2'
BATCH_LIMIT=int(os.getenv('JOB_RADAR_AI_LIMIT','25'))
SCORE_KEYS=['score','responsibility_and_seniority','project_program_delivery','engineering_technical_environment','leadership_and_stakeholders','sector_domain_transferability','critical_infrastructure_availability']
LIST_KEYS=['strongest_matches','gaps_or_risks','hard_barriers','evidence_from_job']; REQUIRED=SCORE_KEYS+['decision','short_reason']+LIST_KEYS
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
 url=f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(MODEL,safe='')}:generateContent?key={urllib.parse.quote(api_key,safe='')}";req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=60) as resp:result=json.loads(resp.read().decode())
 except urllib.error.HTTPError as exc:raise RuntimeError(f"Gemini HTTP {exc.code}: {exc.read().decode(errors='replace')[:800]}") from exc
 candidates=result.get('candidates') or []
 if not candidates:raise RuntimeError('Gemini returned no candidate')
 text=''.join(p.get('text','') for p in candidates[0].get('content',{}).get('parts',[])).strip();return validate(extract_json(text))
def main():
 api_key=os.getenv('GEMINI_API_KEY')
 if not api_key:raise RuntimeError('GEMINI_API_KEY is not configured')
 profile=load_yaml(PROFILE_PATH);criteria=load_yaml(CRITERIA_PATH)
 with connect(DB_PATH) as conn:rows=conn.execute('''SELECT j.*,c.name company FROM jobs j LEFT JOIN companies c ON c.id=j.company_id WHERE NOT EXISTS (SELECT 1 FROM ai_evaluations a WHERE a.job_id=j.id AND a.model_version=?) ORDER BY j.id DESC LIMIT ?''',(EVALUATOR_VERSION,BATCH_LIMIT)).fetchall()
 results=[];errors=0
 for row in rows:
  try:
   ev=evaluate(api_key,profile,criteria,row);ts=now();detail={'short_reason':ev['short_reason'],'evidence_from_job':ev['evidence_from_job'],'profile_version':PROFILE_VERSION,'criteria_version':CRITERIA_VERSION,'provider':'google-gemini','api_model':MODEL}
   with connect(DB_PATH) as conn:conn.execute('''INSERT INTO ai_evaluations(job_id,evaluated_at,model_version,decision,score,profile_match,technical_match,management_match,sector_match,seniority_match,strengths,weaknesses,reasoning,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(row['id'],ts,EVALUATOR_VERSION,ev['decision'],ev['score'],ev['project_program_delivery'],ev['engineering_technical_environment'],ev['leadership_and_stakeholders'],ev['sector_domain_transferability'],ev['responsibility_and_seniority'],json.dumps(ev['strongest_matches'],ensure_ascii=False),json.dumps({'gaps_or_risks':ev['gaps_or_risks'],'hard_barriers':ev['hard_barriers'],'critical_infrastructure_availability':ev['critical_infrastructure_availability']},ensure_ascii=False),json.dumps(detail,ensure_ascii=False),ts))
   results.append({'job':row['public_id'],'score':ev['score'],'decision':ev['decision']})
  except Exception as exc:errors+=1;results.append({'job':row['public_id'],'error':str(exc)})
  time.sleep(.3)
 print(json.dumps({'selected':len(rows),'evaluated':len(rows)-errors,'errors':errors,'results':results},ensure_ascii=False,indent=2));return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())