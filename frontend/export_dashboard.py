"""Export a privacy-minimised JSON snapshot for the static Job Radar frontend.

Only fields needed by the UI leave SQLite. Candidate profile, full descriptions,
internal notes and database internals are deliberately excluded.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from db.database import DB_PATH, connect

OUT = ROOT / "docs" / "data" / "jobs.json"

def main():
    with connect(DB_PATH) as conn:
        rows = conn.execute("""
        WITH latest AS (
          SELECT a.*, ROW_NUMBER() OVER (PARTITION BY a.job_id ORDER BY a.evaluated_at DESC, a.id DESC) rn
          FROM ai_evaluations a
        )
        SELECT j.public_id, j.title, c.name company, c.logo_url,
               j.location, j.workplace_type, j.salary_text, j.first_seen_at,
               l.score, l.decision, l.reasoning,
               js.source_url
        FROM jobs j
        LEFT JOIN companies c ON c.id=j.company_id
        LEFT JOIN latest l ON l.job_id=j.id AND l.rn=1
        LEFT JOIN job_sources js ON js.id=(SELECT id FROM job_sources x WHERE x.job_id=j.id ORDER BY x.last_seen_at DESC, x.id DESC LIMIT 1)
        WHERE l.id IS NOT NULL
        ORDER BY l.score DESC, j.first_seen_at DESC
        """).fetchall()

    jobs=[]
    for r in rows:
        reason=""
        try:
            obj=json.loads(r['reasoning'] or '{}')
            reason=obj.get('short_reason','') if isinstance(obj,dict) else ''
        except Exception:
            pass
        jobs.append({
            'id':r['public_id'],'title':r['title'],'company':r['company'],
            'logo_url':r['logo_url'],'location':r['location'],'workplace_type':r['workplace_type'],
            'salary':r['salary_text'],'first_seen_at':r['first_seen_at'],
            'score':r['score'],'decision':r['decision'],'reason':reason,'url':r['source_url']
        })
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'jobs':jobs},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Exported {len(jobs)} evaluated jobs to {OUT}')

if __name__=='__main__': main()
