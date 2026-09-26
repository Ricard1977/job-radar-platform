import json, urllib.parse
from apply_learning import req, gemini, MODEL, LIMIT
import os

def main():
    key=os.environ.get('GEMINI_API_KEY')
    if not key: raise RuntimeError('GEMINI_API_KEY missing')
    queue=req('GET','learning_reanalysis_requests?status=eq.PENDING&select=id,user_id&order=requested_at.asc&limit=5') or []
    results=[]
    for item in queue:
        rid=int(item['id']); uid=item['user_id']
        try:
            prefs=req('GET','learned_preferences?user_id=eq.'+urllib.parse.quote(uid)+'&select=user_id,profile_version,sample_size,negative_patterns,uncertain_patterns,summary&limit=1') or []
            if not prefs: raise RuntimeError('No learning profile')
            jobs=req('GET',f'jobs?select=id,title,location,workplace_type,description,companies(name)&order=id.desc&limit={LIMIT}') or []
            feedback=req('GET','user_job_feedback?select=job_id,interest,applied') or []
            protected={int(x['job_id']) for x in feedback if x.get('interest')=='INTERESTED' or x.get('applied')}
            candidates=[{'job_id':int(j['id']),'title':j.get('title'),'company':(j.get('companies') or {}).get('name'),'location':j.get('location'),'workplace_type':j.get('workplace_type'),'description':j.get('description')} for j in jobs if int(j['id']) not in protected]
            decisions=gemini(key,prefs[0],candidates) if candidates else []
            valid={x['job_id'] for x in candidates}; archived=[]
            for d in decisions:
                if d.get('action')!='ELIMINAR': continue
                jid=int(d['job_id'])
                if jid not in valid: continue
                pattern=(d.get('pattern') or 'patrón aprendido').strip(); detail=(d.get('reason') or '').strip()
                reason='Eliminada por IA · '+pattern+((' · '+detail) if detail else '')
                req('POST','rpc/archive_and_delete_job_ai',{'p_job_id':jid,'p_reason':reason}); archived.append(jid)
            req('PATCH',f'learning_reanalysis_requests?id=eq.{rid}',{'status':'DONE','completed_at':None,'reviewed_count':len(candidates),'archived_count':len(archived)})
            results.append({'request':rid,'reviewed':len(candidates),'archived':len(archived)})
        except Exception as exc:
            req('PATCH',f'learning_reanalysis_requests?id=eq.{rid}',{'status':'ERROR','error_message':str(exc)[:1000]})
            results.append({'request':rid,'error':str(exc)})
    print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
