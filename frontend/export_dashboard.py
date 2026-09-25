"""Export the evaluated-job snapshot consumed by the static frontend."""
import json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from db.database import DB_PATH,connect
OUT=ROOT/'docs'/'data'/'jobs.json'
def parse(v,default):
 try:return json.loads(v or '')
 except:return default
def main():
 with connect(DB_PATH) as conn:
  rows=conn.execute('''WITH latest AS (SELECT a.*,ROW_NUMBER() OVER(PARTITION BY a.job_id ORDER BY a.evaluated_at DESC,a.id DESC) rn FROM ai_evaluations a) SELECT j.public_id,j.title,j.description,c.name company,c.logo_url,j.location,j.workplace_type,j.salary_text,j.first_seen_at,l.score,l.decision,l.profile_match,l.technical_match,l.management_match,l.sector_match,l.seniority_match,l.strengths,l.weaknesses,l.reasoning,js.source_url,s.name source_name FROM jobs j LEFT JOIN companies c ON c.id=j.company_id LEFT JOIN latest l ON l.job_id=j.id AND l.rn=1 LEFT JOIN job_sources js ON js.id=(SELECT id FROM job_sources x WHERE x.job_id=j.id ORDER BY x.last_seen_at DESC,x.id DESC LIMIT 1) LEFT JOIN sources s ON s.id=js.source_id WHERE l.id IS NOT NULL ORDER BY l.score DESC,j.first_seen_at DESC''').fetchall()
 jobs=[]
 for r in rows:
  reason=parse(r['reasoning'],{});weak=parse(r['weaknesses'],{});strengths=parse(r['strengths'],[])
  jobs.append({'id':r['public_id'],'title':r['title'],'company':r['company'],'logo_url':r['logo_url'],'location':r['location'],'workplace_type':r['workplace_type'],'salary':r['salary_text'],'first_seen_at':r['first_seen_at'],'source':r['source_name'],'url':r['source_url'],'description':r['description'],'score':r['score'],'decision':r['decision'],'reason':reason.get('short_reason',''),'spanish_summary':reason.get('spanish_summary',''),'strengths':strengths if isinstance(strengths,list) else [],'gaps':weak.get('gaps_or_risks',[]) if isinstance(weak,dict) else [],'barriers':weak.get('hard_barriers',[]) if isinstance(weak,dict) else [],'dimensions':{'Gestión de proyectos':r['profile_match'],'Entorno técnico':r['technical_match'],'Liderazgo':r['management_match'],'Sector':r['sector_match'],'Seniority':r['seniority_match']}})
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'jobs':jobs},ensure_ascii=False,indent=2),encoding='utf-8');print(f'Exported {len(jobs)} jobs')
if __name__=='__main__':main()