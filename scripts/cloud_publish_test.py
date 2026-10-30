"""One-off cloud publishing check. No refresh token or provider password is stored."""
import base64, datetime as dt, json, os, sys, time, urllib.request, urllib.error
from zoneinfo import ZoneInfo

OWNER='sts89279308855-web'
REPO='ig-goog-lesheets'
ACCOUNT='instagram_tented-tyke'
IG_USER='29193469003673474'
STATE_PATH='.cloud/instagram-test.json'
UTC=dt.timezone.utc

class MCP:
 def __init__(self,token,consumer=False):
  self.token=token;self.consumer=consumer;self.sid=None;self.counter=0;self.tool_session='play'
  r=self.request('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'instagram-cloud-test','version':'1.0'}})
  self.version=r.get('result',{}).get('protocolVersion','2025-03-26')
 def request(self,method,params):
  self.counter+=1
  body=json.dumps({'jsonrpc':'2.0','id':self.counter,'method':method,'params':params}).encode()
  h={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
  h['x-consumer-api-key' if self.consumer else 'Authorization']=self.token if self.consumer else 'Bearer '+self.token
  if self.sid:h['Mcp-Session-Id']=self.sid
  if hasattr(self,'version'):h['MCP-Protocol-Version']=self.version
  req=urllib.request.Request('https://connect.composio.dev/mcp',data=body,headers=h,method='POST')
  try:
   with urllib.request.urlopen(req,timeout=180) as r:
    self.sid=r.headers.get('Mcp-Session-Id',self.sid);raw=r.read().decode()
  except urllib.error.HTTPError as e:raise RuntimeError('MCP HTTP '+str(e.code)) from None
  try:response=json.loads(raw)
  except json.JSONDecodeError:
   events=[line[5:].strip() for line in raw.splitlines() if line.startswith('data:')]
   response=next(json.loads(v) for v in reversed(events) if v.startswith('{') and ('"result"' in v or '"error"' in v))
  if 'error' in response:raise RuntimeError('MCP request rejected')
  return response
 def tool(self,name,args):
  r=self.request('tools/call',{'name':'COMPOSIO_MULTI_EXECUTE_TOOL','arguments':{'session_id':self.tool_session,'current_step':'CLOUD_PUBLISH','sync_response_to_workbench':False,'tools':[{'tool_slug':name,'account':ACCOUNT,'arguments':args}]}})['result']
  if r.get('isError'):raise RuntimeError('MCP tool failed: '+name)
  result=json.loads(next(c['text'] for c in r['content'] if c.get('type')=='text'))
  entry=result.get('data',{}).get('results',[{}])[0].get('response',{})
  if 'data' not in entry:raise RuntimeError('Incomplete provider response; refusing to continue: '+name)
  data=entry.get('data',{})
  if not entry.get('successful') or data.get('http_error') or int(data.get('status_code',200))>=400:
   raise RuntimeError('Provider tool failed: '+name)
  return data

def gh(path,method='GET',body=None):
 url='https://api.github.com/repos/'+OWNER+'/'+REPO+'/'+path
 h={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'instagram-cloud-test'}
 data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
 req=urllib.request.Request(url,data=data,headers=h,method=method)
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
 except urllib.error.HTTPError as e:
  if e.code==404 and method=='GET':return None
  raise RuntimeError('GitHub HTTP '+str(e.code)) from None

def read_file(path):
 r=gh('contents/'+path+'?ref=main')
 return (base64.b64decode(r['content']).decode(),r['sha']) if r else (None,None)
def change_file(path,transform,message):
 for attempt in range(3):
  old,sha=read_file(path);text=transform(old)
  body={'message':message,'branch':'main','content':base64.b64encode(text.encode()).decode()}
  if sha:body['sha']=sha
  try:return gh('contents/'+path,'PUT',body)
  except RuntimeError as e:
   if str(e)!='GitHub HTTP 409' or attempt==2:raise
 return None
def state(**fields):
 base={'test_id':os.environ['TEST_ID'],'target_utc':os.environ['TARGET_UTC'],'container_id':os.environ['CONTAINER_ID'],'reel_id':os.environ['REEL_ID'],'run_url':os.environ['RUN_URL'],'updated_at':dt.datetime.now(UTC).isoformat()}
 base.update(fields)
 change_file(STATE_PATH,lambda _:json.dumps(base,ensure_ascii=False,indent=2),'Record cloud Instagram test: '+fields.get('status','update'))
 return base

def profile(m):
 p=m.tool('INSTAGRAM_GET_USER_INFO',{'ig_user_id':'me','fields':'id,username'})
 if p.get('username')!='goog.lesheets' or p.get('id')!=IG_USER:raise RuntimeError('Unexpected publishing account')
 return p

def preflight():
 target=dt.datetime.fromisoformat(os.environ['TARGET_UTC'].replace('Z','+00:00'))
 remaining=(target-dt.datetime.now(UTC)).total_seconds()
 if not 120<remaining<1800:raise RuntimeError('Test must be 2–30 minutes in the future')
 if target.timestamp()+300>=int(os.environ['ACCESS_EXPIRES_AT_MS'])/1000:raise RuntimeError('Temporary access expires too soon')
 m=MCP(os.environ['COMPOSIO_MCP_TOKEN']);p=profile(m)
 old,_=read_file(STATE_PATH)
 if old and json.loads(old).get('test_id')==os.environ['TEST_ID'] and json.loads(old).get('status')=='published':raise RuntimeError('This test has already published')
 state(status='waiting',verified_account=p['username'],message='Cloud runner verified; waiting for the publication time.')
 print('CLOUD_READY',p['username'],os.environ['TARGET_UTC'],flush=True)

def published_by_caption(m,caption):
 d=m.tool('INSTAGRAM_GET_IG_USER_MEDIA',{'ig_user_id':'me','limit':25,'fields':'id,caption,permalink,timestamp'})
 return next((e for e in d.get('data',[]) if e.get('caption','')==caption),None)

def record_success(media,warnings=None):
 local_date=dt.datetime.fromisoformat(media['timestamp'].replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Yekaterinburg')).date()
 def update_queue(old):
  q=json.loads(old);e=next(v for v in q if v['id']==os.environ['REEL_ID'])
  e.update(status='published',media_id=media['id'],permalink=media['permalink'],published_date=local_date.isoformat(),cloud_test_id=os.environ['TEST_ID'])
  fixed={v['date'] for v in q if v.get('status') in ('ready','planned') and (v.get('format')=='lesson' or v.get('status')=='planned')}
  day=local_date+dt.timedelta(days=1)
  for v in sorted((v for v in q if v.get('status')=='ready' and v.get('format')!='lesson'),key=lambda v:v['date']):
   while day.isoformat() in fixed:day+=dt.timedelta(days=1)
   v['date']=day.isoformat();fixed.add(v['date']);day+=dt.timedelta(days=1)
  return json.dumps(q,ensure_ascii=False,indent=2)
 change_file('queue.json',update_queue,'Record cloud-published '+os.environ['REEL_ID'])
 line='\n- '+local_date.strftime('%d.%m')+' — разовый облачный тест GitHub Actions: '+os.environ['REEL_ID']+' опубликован, '+media['permalink']+' . Запуск: '+os.environ['RUN_URL']+' . test_id='+os.environ['TEST_ID']+'\n'
 change_file('journal.md',lambda old:old if os.environ['TEST_ID'] in (old or '') else (old or '')+line,'Log successful cloud publishing test')
 state(status='published',media_id=media['id'],permalink=media['permalink'],published_at=media['timestamp'],warnings=warnings or [])

def publish():
 target=dt.datetime.fromisoformat(os.environ['TARGET_UTC'].replace('Z','+00:00'))
 while True:
  remaining=(target-dt.datetime.now(UTC)).total_seconds()
  if remaining<=0:break
  time.sleep(min(remaining,20))
 if (dt.datetime.now(UTC)-target).total_seconds()>300:raise RuntimeError('Test slot missed; do not post late')
 old,_=read_file(STATE_PATH)
 if not old or json.loads(old).get('test_id')!=os.environ['TEST_ID']:raise RuntimeError('Test state changed')
 if json.loads(old).get('status')=='published':print('Already published; exiting');return
 q,_=read_file('queue.json');entry=next(e for e in json.loads(q) if e['id']==os.environ['REEL_ID']);caption=entry['caption'].replace('\\n','\n')
 m=MCP(os.environ['COMPOSIO_MCP_TOKEN']);profile(m)
 found=published_by_caption(m,caption)
 if found:
  record_success(found,['Existing matching media found; no second publication was sent.']);return
 if entry.get('status')!='ready':raise RuntimeError('Queue entry is no longer ready')
 state(status='publishing',message='Publishing the pre-created container once.')
 try:
  r=m.tool('INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH',{'ig_user_id':IG_USER,'creation_id':os.environ['CONTAINER_ID'],'max_wait_seconds':150})
  mid=r['id']
 except Exception:
  time.sleep(15);found=published_by_caption(m,caption)
  if found:record_success(found,['Publication response was unclear; matching media was verified.']);return
  state(status='unknown',message='Publication response was unclear. Verify account before retrying.');raise RuntimeError('Uncertain publish result; not retrying') from None
 media=m.tool('INSTAGRAM_GET_IG_MEDIA',{'ig_media_id':mid,'fields':'id,permalink,timestamp,caption'})
 warnings=[]
 if entry.get('hashtags'):
  try:m.tool('INSTAGRAM_POST_IG_MEDIA_COMMENTS',{'ig_media_id':mid,'message':entry['hashtags']})
  except Exception:warnings.append('Hashtag comment could not be confirmed. Do not republish media.')
 record_success(media,warnings)
 print('PUBLISHED',media['permalink'],flush=True)

if __name__=='__main__':
 try:
  if sys.argv[1]=='--preflight':preflight()
  elif sys.argv[1]=='--run':publish()
  else:raise RuntimeError('Unknown mode')
 except Exception as e:
  print('FAILED',type(e).__name__,str(e),flush=True)
  if os.environ.get('GH_TOKEN'):
   try:state(status='failed',message=type(e).__name__+': '+str(e))
   except Exception:pass
  raise SystemExit(1)
