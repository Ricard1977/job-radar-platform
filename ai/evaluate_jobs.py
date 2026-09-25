"""MVP AI evaluator: SQLite jobs -> OpenAI -> ai_evaluations.

Only evaluates jobs that do not yet have an evaluation for the current
profile/criteria version. Results are persisted transactionally.
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from openai import OpenAI
import yaml

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from db.database import DB_PATH, connect

PROFILE_PATH=ROOT/'config'/'candidate_profile_v0.yaml'
CRITERIA_PATH=ROOT/'config'/'evaluation_criteria_v0.yaml'
MODEL=os.getenv('JOB_RADAR_AI_MODEL','gpt-5.6-luna')
PROFILE_VERSION='0'; CRITERIA_VERSION='0'; EVALUATOR_VERSION=f'profile-{PROFILE_VERSION}_criteria-{CRITERIA_VERSION}'
BATCH_LIMIT=int(os.getenv('JOB_RADAR_AI_LIMIT','200'))

SCHEMA={
 'type':'object','additionalProperties':False,
 'properties':{
  'score':{'type':'number','minimum':0,'maximum':100},
  'decision':{'type':'string','enum':['HIGH_INTEREST','INTERESTING','REVIEW','LOW_INTEREST']},
  'responsibility_and_seniority':{'type':'number','minimum':0,'maximum':100},
  'project_program_delivery':{'type':'number','minimum':0,'maximum':100},
  'engineering_technical_environment':{'type':'number','minimum':0,'maximum':100},
  'leadership_and_stakeholders':{'type':'number','minimum':0,'maximum':100},
  'sector_domain_transferability':{'type':'number','minimum':0,'maximum':100},
  'critical_infrastructure_availability':{'type':'number','minimum':0,'maximum':100},
  'short_reason':{'type':'string'},
  'strongest_matches':{'type':'array','items':{'type':'string'}},
  'gaps_or_risks':{'type':'array','items':{'type':'string'}},
  'hard_barriers':{'type':'array','items':{'type':'string'}},
  'evidence_from_job':{'type':'array','items':{'type':'string'}}
 },
 'required':['score','decision','responsibility_and_seniority','project_program_delivery','engineering_technical_environment','leadership_and_stakeholders','sector_domain_transferability','critical_infrastructure_availability','short_reason','strongest_matches','gaps_or_risks','hard_barriers','evidence_from_job']
}

def now(): return datetime.now(timezone.utc).isoformat()
def load_yaml(path): return yaml.safe_load(path.read_text(encoding='utf-8'))
def compact_job(row):
 return {'public_id':row['public_id'],'title':row['title'],'company':row['company'],'location':row['location'],'workplace_type':row['workplace_type'],'salary_text':row['salary_text'],'description':row['description']}
def evaluate(client,profile,criteria,row):
 payload={'candidate_profile':profile,'evaluation_criteria':criteria,'job':compact_job(row)}
 instructions='''You are the first-pass evaluator for a job radar. Evaluate fit, do not decide for the candidate. Follow the supplied profile and criteria exactly. Read the complete description, not just the title. Distinguish missing evidence from mismatch. Do not invent facts. Use the configured dimension weights to derive a coherent 0-100 overall score and apply the configured decision bands. Keep reasons concise and evidence-based.'''
 response=client.responses.create(model=MODEL,instructions=instructions,input=json.dumps(payload,ensure_ascii=False),text={'format':{'type':'json_schema','name':'job_evaluation','strict':True,'schema':SCHEMA}})
 return json.loads(response.output_text)

def main():
 if not os.getenv('OPENAI_API_KEY'): raise RuntimeError('OPENAI_API_KEY is not configured')
 profile=load_yaml(PROFILE_PATH); criteria=load_yaml(CRITERIA_PATH); client=OpenAI()
 with connect(DB_PATH) as conn:
  rows=conn.execute('''SELECT j.*,c.name company FROM jobs j LEFT JOIN companies c ON c.id=j.company_id
   WHERE NOT EXISTS (SELECT 1 FROM ai_evaluations a WHERE a.job_id=j.id AND a.model_version=?) ORDER BY j.id DESC LIMIT ?''',(EVALUATOR_VERSION,BATCH_LIMIT)).fetchall()
 total=len(rows); ok=errors=0; results=[]
 for row in rows:
  try:
   ev=evaluate(client,profile,criteria,row); ts=now()
   with connect(DB_PATH) as conn:
    conn.execute('''INSERT INTO ai_evaluations(job_id,evaluated_at,model_version,decision,score,profile_match,technical_match,management_match,sector_match,seniority_match,strengths,weaknesses,reasoning,created_at)
     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(row['id'],ts,EVALUATOR_VERSION,ev['decision'],ev['score'],ev['project_program_delivery'],ev['engineering_technical_environment'],ev['leadership_and_stakeholders'],ev['sector_domain_transferability'],ev['responsibility_and_seniority'],json.dumps(ev['strongest_matches'],ensure_ascii=False),json.dumps({'gaps_or_risks':ev['gaps_or_risks'],'hard_barriers':ev['hard_barriers'],'critical_infrastructure_availability':ev['critical_infrastructure_availability']},ensure_ascii=False),json.dumps({'short_reason':ev['short_reason'],'evidence_from_job':ev['evidence_from_job'],'profile_version':PROFILE_VERSION,'criteria_version':CRITERIA_VERSION,'api_model':MODEL},ensure_ascii=False),ts))
   ok+=1; results.append({'job':row['public_id'],'score':ev['score'],'decision':ev['decision'],'reason':ev['short_reason']})
  except Exception as exc:
   errors+=1; results.append({'job':row['public_id'],'error':f'{type(exc).__name__}: {exc}'})
  time.sleep(.1)
 summary={'model':MODEL,'evaluator_version':EVALUATOR_VERSION,'selected':total,'evaluated':ok,'errors':errors,'results':results}
 print(json.dumps(summary,ensure_ascii=False,indent=2)); return 1 if errors else 0
if __name__=='__main__': raise SystemExit(main())
