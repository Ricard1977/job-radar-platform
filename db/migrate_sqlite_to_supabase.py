"""One-way initial migration from the existing SQLite registry to Supabase.

Requires SUPABASE_URL and SUPABASE_SECRET_KEY. Idempotent for natural keys.
"""
import json, os, sqlite3, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'data'/'job_radar.db'
URL=os.environ['SUPABASE_URL'].rstrip('/')
KEY=os.environ['SUPABASE_SECRET_KEY']
HEADERS={'apikey':KEY,'Authorization':f'Bearer {KEY}','Content-Type':'application/json','Prefer':'return=representation'}

def req(method, table, body=None, query=''):
    url=f'{URL}/rest/v1/{table}{query}'
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
    r=urllib.request.Request(url,data=data,headers=HEADERS,method=method)
    try:
        with urllib.request.urlopen(r,timeout=60) as x:
            raw=x.read().decode(); return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{table}: HTTP {e.code}: {e.read().decode(errors="replace")[:1000]}') from e

def rows(conn, table):
    try:return [dict(x) for x in conn.execute(f'SELECT * FROM {table}')]
    except sqlite3.OperationalError:return []

def clean(d, allowed):return {k:d.get(k) for k in allowed if k in d}
def upsert(table, records, conflict):
    if not records:return []
    h=dict(HEADERS);h['Prefer']='resolution=merge-duplicates,return=representation'
    url=f'{URL}/rest/v1/{table}?on_conflict={urllib.parse.quote(conflict)}'
    r=urllib.request.Request(url,data=json.dumps(records,ensure_ascii=False).encode(),headers=h,method='POST')
    try:
        with urllib.request.urlopen(r,timeout=60) as x:return json.loads(x.read().decode() or '[]')
    except urllib.error.HTTPError as e:raise RuntimeError(f'{table}: HTTP {e.code}: {e.read().decode(errors="replace")[:1000]}') from e

def main():
    if not DB.exists():raise SystemExit(f'Missing {DB}')
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
    src=upsert('sources',[clean(x,['code','name','source_type','enabled']) for x in rows(c,'sources')],'code')
    companies=upsert('companies',[clean(x,['name','website','linkedin_url','logo_url','sector','location','created_at','updated_at']) for x in rows(c,'companies')],'name')
    source_ids={x['code']:x['id'] for x in req('GET','sources',query='?select=id,code')}; company_ids={x['name']:x['id'] for x in req('GET','companies',query='?select=id,name')}
    old_comp={x['id']:x['name'] for x in rows(c,'companies')}; old_src={x['id']:x['code'] for x in rows(c,'sources')}
    jobs=[]
    for x in rows(c,'jobs'):
        y=clean(x,['public_id','title','location','workplace_type','description','salary_text','salary_min','salary_max','salary_currency','salary_period','status','status_reason','first_seen_at','updated_at']);y['company_id']=company_ids.get(old_comp.get(x.get('company_id')));jobs.append(y)
    upsert('jobs',jobs,'public_id'); job_ids={x['public_id']:x['id'] for x in req('GET','jobs',query='?select=id,public_id')}; old_jobs={x['id']:x['public_id'] for x in rows(c,'jobs')}
    js=[]
    for x in rows(c,'job_sources'):
        y=clean(x,['external_job_id','source_url','first_seen_at','last_seen_at','seen_count','active']);y['job_id']=job_ids.get(old_jobs.get(x.get('job_id')));y['source_id']=source_ids.get(old_src.get(x.get('source_id')));js.append(y)
    upsert('job_sources',js,'source_id,external_job_id')
    ev=[]
    for x in rows(c,'ai_evaluations'):
        y=clean(x,['evaluated_at','model_version','decision','score','profile_match','technical_match','management_match','sector_match','seniority_match','strengths','weaknesses','reasoning','created_at']);y['job_id']=job_ids.get(old_jobs.get(x.get('job_id')))
        for k in ('strengths','weaknesses','reasoning'):
            if isinstance(y.get(k),str):
                try:y[k]=json.loads(y[k])
                except Exception:y[k]={'text':y[k]}
        ev.append(y)
    # Evaluations have no natural unique key in migration 001, so insert only when destination is empty.
    existing=req('GET','ai_evaluations',query='?select=id&limit=1')
    if ev and not existing:req('POST','ai_evaluations',ev)
    print(json.dumps({'sources':len(src),'companies':len(companies),'jobs':len(jobs),'job_sources':len(js),'ai_evaluations':len(ev)},indent=2))
if __name__=='__main__':main()
