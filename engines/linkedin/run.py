"""Production LinkedIn ingestion pipeline backed by SQLite."""
import json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[2]; ENGINE_DIR=Path(__file__).resolve().parent; sys.path.insert(0,str(ROOT))
from core.raw_batch import delete_processed_raw, read_raw_batch, write_raw_batch
from db.database import DB_PATH, connect, initialize
from engines.linkedin.core.public_extractor import fetch_public_jobs, jobs_as_dicts
from engines.linkedin.input.search_config import load_searches
CONFIG_PATH=ENGINE_DIR/'config'/'searches.yaml'; RAW_DIR=ROOT/'data'/'linkedin'/'raw'; MAX_RESULTS_PER_SEARCH=1000; PAGE_SIZE=25; EMPTY_PAGE_STOP=2; DETAIL_DELAY_SECONDS=1.0

def utcnow(): return datetime.now(timezone.utc).isoformat()
def clean(x): return ' '.join(x.get_text(' ',strip=True).split()) if x else None

def fetch_all(search):
    by_id={}; empty=0; start=0; truncated=False
    while start<MAX_RESULTS_PER_SEARCH:
        page=fetch_public_jobs(search,start=start)
        if not page:
            empty+=1
            if empty>=EMPTY_PAGE_STOP: break
        else:
            empty=0
            for job in page: by_id[job.job_id]=job
            if len(by_id)>=MAX_RESULTS_PER_SEARCH: truncated=True; break
        start+=PAGE_SIZE; time.sleep(.5)
    return list(by_id.values())[:MAX_RESULTS_PER_SEARCH],truncated

def parse_salary(text):
    if not text: return None,None,None,None
    currency='EUR' if ('€' in text or 'EUR' in text.upper()) else ('USD' if ('$' in text or 'USD' in text.upper()) else ('GBP' if ('£' in text or 'GBP' in text.upper()) else None)
    period='year' if re.search(r'/\s*(?:yr|year|año)|per year|al año',text,re.I) else ('hour' if re.search(r'/\s*(?:hr|hour|h)|per hour|hora',text,re.I) else ('month' if re.search(r'/\s*(?:mo|month)|per month|mes',text,re.I) else None))
    vals=[]
    for n,k in re.findall(r'([0-9]+(?:[.,][0-9]+)?)\s*([kK]?)',text):
        try:
            v=float(n.replace(',','.')); vals.append(v*1000 if k else v)
        except ValueError: pass
    vals=[v for v in vals if v>=5]
    return (vals[0] if vals else None),(vals[1] if len(vals)>1 else (vals[0] if vals else None)),currency,period

def fetch_detail(job_id):
    url=f'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}'
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/136.0 Safari/537.36'},timeout=20); r.raise_for_status(); soup=BeautifulSoup(r.text,'html.parser')
    criteria={}
    for item in soup.select('li.description__job-criteria-item'):
        label=clean(item.select_one('h3.description__job-criteria-subheader')); value=clean(item.select_one('span.description__job-criteria-text'))
        if label: criteria[label]=value
    all_text=clean(soup) or ''
    workplace=None
    for candidate in ['Remote','Hybrid','On-site','En remoto','Híbrido','Presencial']:
        if re.search(r'\b'+re.escape(candidate)+r'\b',all_text,re.I): workplace={'remote':'REMOTE','en remoto':'REMOTE','hybrid':'HYBRID','híbrido':'HYBRID','on-site':'ONSITE','presencial':'ONSITE'}[candidate.lower()]; break
    salary_el=soup.select_one('.compensation__salary-range') or soup.select_one('.salary')
    salary_text=clean(salary_el)
    if not salary_text:
        m=re.search(r'(?:(?:EUR|USD|GBP)\s*)?[€$£]?\s*\d[\d.,]*\s*[kK]?\s*(?:-|–|—|to|a)\s*(?:(?:EUR|USD|GBP)\s*)?[€$£]?\s*\d[\d.,]*\s*[kK]?(?:\s*/\s*(?:yr|year|año|hr|hour|h|month|mo|mes))?',all_text,re.I)
        salary_text=m.group(0).strip() if m else None
    smin,smax,currency,period=parse_salary(salary_text)
    company=soup.select_one('a.topcard__org-name-link'); logo=soup.select_one('img.artdeco-entity-image') or soup.select_one('img')
    return {'description':clean(soup.select_one('div.show-more-less-html__markup')),'company_url':company.get('href') if company else None,'company_logo_url':(logo.get('data-delayed-url') or logo.get('src')) if logo else None,'job_criteria':criteria,'workplace_type':workplace,'salary_text':salary_text,'salary_min':smin,'salary_max':smax,'salary_currency':currency,'salary_period':period}

def source_id(conn,code='linkedin'): return conn.execute('SELECT id FROM sources WHERE code=?',(code,)).fetchone()['id']
def ensure_search(conn,s,src):
    row=conn.execute('SELECT id FROM searches WHERE public_id=?',(s.search_id,)).fetchone()
    if row:return row['id']
    return conn.execute('INSERT INTO searches(public_id,source_id,name,keywords,location,date_filter,enabled,created_at) VALUES(?,?,?,?,?,?,1,?)',(s.search_id,src,s.search_id,s.keywords,s.location,s.date_posted,utcnow())).lastrowid
def ensure_company(conn,name,d):
    if not name:return None
    row=conn.execute('SELECT id FROM companies WHERE name=?',(name,)).fetchone()
    if row:
        conn.execute('UPDATE companies SET linkedin_url=COALESCE(linkedin_url,?),logo_url=COALESCE(logo_url,?),updated_at=? WHERE id=?',(d.get('company_url'),d.get('company_logo_url'),utcnow(),row['id'])); return row['id']
    return conn.execute('INSERT INTO companies(name,linkedin_url,logo_url,created_at,updated_at) VALUES(?,?,?,?,?)',(name,d.get('company_url'),d.get('company_logo_url'),utcnow(),utcnow())).lastrowid
def next_public_id(conn):
    row=conn.execute("SELECT MAX(CAST(SUBSTR(public_id,4) AS INTEGER)) n FROM jobs WHERE public_id LIKE 'JR-%'").fetchone(); return f"JR-{(row['n'] or 0)+1:06d}"

def process_search(search):
    rid='LIN-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); raw_path=RAW_DIR/f'{rid}.json'; initialize(DB_PATH)
    with connect(DB_PATH) as conn:
        src=source_id(conn); sid=ensure_search(conn,search,src); run_id=conn.execute("INSERT INTO runs(public_id,search_id,source_id,started_at,status,processed) VALUES(?,?,?,?,?,0)",(rid,sid,src,utcnow(),'RUNNING')).lastrowid
    try:
        cards,truncated=fetch_all(search); unique={j.job_id:j for j in cards}; write_raw_batch(raw_path,{'run_id':rid,'source':'linkedin','created_at':utcnow(),'search_id':search.search_id,'truncated':truncated,'jobs':jobs_as_dicts(list(unique.values()))}); batch=read_raw_batch(raw_path)
        imported=known=errors=enriched=0; error_items=[]
        with connect(DB_PATH) as conn:
            src=source_id(conn)
            for raw in batch['jobs']:
                ext=str(raw['job_id']); existing=conn.execute('SELECT id,job_id FROM job_sources WHERE source_id=? AND external_job_id=?',(src,ext)).fetchone()
                if existing:
                    conn.execute('UPDATE job_sources SET last_seen_at=?,seen_count=seen_count+1,active=1 WHERE id=?',(utcnow(),existing['id'])); known+=1
                    row=conn.execute('SELECT workplace_type,salary_text FROM jobs WHERE id=?',(existing['job_id'],)).fetchone()
                    if row and (not row['workplace_type'] or not row['salary_text']):
                        try:
                            d=fetch_detail(ext); conn.execute('UPDATE jobs SET workplace_type=COALESCE(workplace_type,?),salary_text=COALESCE(salary_text,?),salary_min=COALESCE(salary_min,?),salary_max=COALESCE(salary_max,?),salary_currency=COALESCE(salary_currency,?),salary_period=COALESCE(salary_period,?),updated_at=? WHERE id=?',(d['workplace_type'],d['salary_text'],d['salary_min'],d['salary_max'],d['salary_currency'],d['salary_period'],utcnow(),existing['job_id'])); enriched+=1; time.sleep(DETAIL_DELAY_SECONDS)
                        except Exception: pass
                    continue
                d={}; err=None
                try:d=fetch_detail(ext)
                except Exception as exc: err=f'{type(exc).__name__}: {exc}'; errors+=1
                cid=ensure_company(conn,raw.get('company'),d); pub=next_public_id(conn); created=utcnow()
                jid=conn.execute("INSERT INTO jobs(public_id,company_id,title,location,workplace_type,description,salary_text,salary_min,salary_max,salary_currency,salary_period,status,status_reason,first_seen_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,'NEW',?,?,?)",(pub,cid,raw.get('title'),raw.get('location'),d.get('workplace_type'),d.get('description'),d.get('salary_text'),d.get('salary_min'),d.get('salary_max'),d.get('salary_currency'),d.get('salary_period'),err,created,created)).lastrowid
                conn.execute('INSERT INTO job_sources(job_id,source_id,external_job_id,source_url,first_seen_at,last_seen_at,seen_count,active) VALUES(?,?,?,?,?,?,1,1)',(jid,src,ext,raw.get('job_url'),created,created)); conn.execute('INSERT INTO job_events(job_id,event_type,event_date,new_value,reason,actor,created_at) VALUES(?,?,?,?,?,?,?)',(jid,'DISCOVERED',created,'NEW',f'Discovered via {search.search_id}','linkedin-engine',created)); imported+=1
                if err:error_items.append({'public_id':pub,'source_job_id':ext,'error':err})
                time.sleep(DETAIL_DELAY_SECONDS)
            warning='MAX_RESULTS_REACHED' if truncated else None
            conn.execute("UPDATE runs SET finished_at=?,status='SUCCESS',records_found=?,unique_records=?,new_jobs=?,known_jobs=?,detail_errors=?,truncated=?,processed=1,error_description=?,raw_file=? WHERE id=?",(utcnow(),len(cards),len(unique),imported,known,errors,int(truncated),json.dumps({'warning':warning,'detail_errors':error_items,'known_jobs_enriched':enriched},ensure_ascii=False) if warning or error_items or enriched else None,str(raw_path),run_id))
        delete_processed_raw(raw_path); return {'run_id':rid,'search_id':search.search_id,'status':'SUCCESS','records':len(unique),'new':imported,'known':known,'known_enriched':enriched,'detail_errors':errors,'warning':'MAX_RESULTS_REACHED' if truncated else None}
    except Exception as exc:
        with connect(DB_PATH) as conn: conn.execute("UPDATE runs SET finished_at=?,status='ERROR',processed=0,error_type=?,error_description=?,raw_file=? WHERE id=?",(utcnow(),type(exc).__name__,str(exc),str(raw_path) if raw_path.exists() else None,run_id))
        return {'run_id':rid,'search_id':search.search_id,'status':'ERROR','error':f'{type(exc).__name__}: {exc}','raw_preserved':raw_path.exists()}
def main():
    results=[process_search(s) for s in load_searches(CONFIG_PATH)]; print(json.dumps({'executed_at':utcnow(),'database':str(DB_PATH),'results':results},ensure_ascii=False,indent=2)); return 1 if any(x['status']=='ERROR' for x in results) else 0
if __name__=='__main__': raise SystemExit(main())
