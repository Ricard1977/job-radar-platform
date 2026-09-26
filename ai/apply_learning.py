"""Reevaluate pending Supabase jobs with Gemini + learned preferences.
Archives only clear learned-preference rejects. AI decisions never create human learning signals.
"""
import json, os, urllib.error, urllib.parse, urllib.request

MODEL=os.getenv('JOB_RADAR_AI_MODEL','gemini-3.5-flash-lite')
LIMIT=int(os.getenv('JOB_RADAR_LEARNING_LIMIT','200'))

def req(method,path,body=None,prefer=None):
    base=os.environ['SUPABASE_URL'].rstrip('/'); key=os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not key: raise RuntimeError('SUPABASE_SECRET_KEY missing')
    h={'apikey':key,'Authorization':f'Bearer {key}','Content-Type':'application/json'}
    if prefer:h['Prefer']=prefer
    data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    r=urllib.request.Request(base+'/rest/v1/'+path,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(r,timeout=90) as x:
            raw=x.read().decode(); return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e: raise RuntimeError(f'Supabase {e.code}: {e.read().decode(errors="replace")[:800]}') from e

def gemini(key,preferences,jobs):
    prompt='''Eres el filtro de aprendizaje de Job Radar. Debes decidir para CADA oferta si el aprendizaje explícito del usuario permite descartarla con seguridad. No hagas coincidencia simple de palabras. Lee título y descripción y entiende la función real. Un término incidental (por ejemplo SAP, IT, cloud, engineer) NO basta. Elimina solo cuando la naturaleza principal del puesto coincide claramente con un patrón negativo aprendido. Si hay ambigüedad, MANTENER. No uses tus propias decisiones como nuevo aprendizaje. Devuelve JSON.\n\n'''+json.dumps({'learned_preferences':preferences,'jobs':jobs},ensure_ascii=False)
    schema={'type':'OBJECT','properties':{'decisions':{'type':'ARRAY','items':{'type':'OBJECT','properties':{'job_id':{'type':'INTEGER'},'action':{'type':'STRING','enum':['MANTENER','ELIMINAR']},'pattern':{'type':'STRING'},'reason':{'type':'STRING'}},'required':['job_id','action','pattern','reason']}}},'required':['decisions']}
    body={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseMimeType':'application/json','responseJsonSchema':schema,'temperature':0}}
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(MODEL,safe="")}:generateContent?key={urllib.parse.quote(key,safe="")}'
    r=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(r,timeout=120) as x: out=json.loads(x.read().decode())
    except urllib.error.HTTPError as e: raise RuntimeError(f'Gemini {e.code}: {e.read().decode(errors="replace")[:800]}') from e
    text=''.join(p.get('text','') for p in out['candidates'][0]['content']['parts']); return json.loads(text)['decisions']

def main():
    gkey=os.environ.get('GEMINI_API_KEY')
    if not gkey: raise RuntimeError('GEMINI_API_KEY missing')
    prefs=req('GET','learned_preferences?select=user_id,profile_version,sample_size,negative_patterns,uncertain_patterns,summary&order=updated_at.desc&limit=1') or []
    if not prefs: print(json.dumps({'status':'no_learning_profile'})); return
    # Only jobs still present are candidates; interested/applied are excluded below.
    jobs=req('GET',f'jobs?select=id,title,location,workplace_type,description,companies(name)&order=id.desc&limit={LIMIT}') or []
    feedback=req('GET','user_job_feedback?select=job_id,interest,applied') or []
    protected={int(x['job_id']) for x in feedback if x.get('interest')=='INTERESTED' or x.get('applied')}
    candidates=[{'job_id':int(j['id']),'title':j.get('title'),'company':(j.get('companies') or {}).get('name'),'location':j.get('location'),'workplace_type':j.get('workplace_type'),'description':j.get('description')} for j in jobs if int(j['id']) not in protected]
    decisions=gemini(gkey,prefs[0],candidates) if candidates else []
    archived=[]
    for d in decisions:
        if d.get('action')!='ELIMINAR': continue
        jid=int(d['job_id'])
        if jid not in {x['job_id'] for x in candidates}: continue
        pattern=(d.get('pattern') or 'patrón aprendido').strip(); detail=(d.get('reason') or '').strip()
        reason=f'Eliminada por IA · {pattern}'+(f' · {detail}' if detail else '')
        req('POST','rpc/archive_and_delete_job_ai',{'p_job_id':jid,'p_reason':reason})
        archived.append({'job_id':jid,'pattern':pattern,'reason':detail})
    print(json.dumps({'reviewed':len(candidates),'archived':len(archived),'archived_jobs':archived},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
