"""Isolated Gemini evaluator smoke test. No database access."""
import json, os, time, urllib.error, urllib.parse, urllib.request
MODEL=os.getenv('JOB_RADAR_AI_MODEL','gemini-3.5-flash-lite')
KEY=os.environ['GEMINI_API_KEY']
SAMPLES=[
 {'title':'Senior Project Manager - Critical Infrastructure','description':'Lead engineering projects for critical facilities, automation, SCADA, BMS, commissioning and stakeholders.'},
 {'title':'Engineering Manager - Industrial Automation','description':'Lead PLC SCADA automation engineering team, project delivery, commissioning and suppliers.'},
 {'title':'Junior Marketing Assistant','description':'Entry-level social media and marketing support role.'}
]
def call(sample):
 prompt='Return JSON with score 0-100 and reason for fit with a senior project management, engineering, automation and critical infrastructure profile. JOB='+json.dumps(sample)
 body={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseMimeType':'application/json'}}
 url='https://generativelanguage.googleapis.com/v1beta/models/'+urllib.parse.quote(MODEL,safe='')+':generateContent?key='+urllib.parse.quote(KEY,safe='')
 start=time.monotonic(); req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=45) as r:data=json.loads(r.read().decode())
  text=''.join(p.get('text','') for p in data['candidates'][0]['content']['parts']); result=json.loads(text)
  return {'ok':True,'http':200,'seconds':round(time.monotonic()-start,2),'result':result}
 except urllib.error.HTTPError as e:return {'ok':False,'http':e.code,'seconds':round(time.monotonic()-start,2),'error':e.read().decode(errors='replace')[:300]}
 except Exception as e:return {'ok':False,'http':None,'seconds':round(time.monotonic()-start,2),'error':repr(e)}
def main():
 results=[]
 for i,s in enumerate(SAMPLES,1):
  r=call(s);r['sample']=i;results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True);time.sleep(1)
 ok=sum(x['ok'] for x in results);print('SUMMARY '+json.dumps({'model':MODEL,'tests':len(results),'success':ok,'failed':len(results)-ok,'http_503':sum(x.get('http')==503 for x in results)}),flush=True)
 raise SystemExit(0 if ok==len(results) else 1)
if __name__=='__main__':main()
