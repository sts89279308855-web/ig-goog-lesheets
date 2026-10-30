"""Daily cloud publishing plus replenishment from reviewed teaching templates."""
import base64,datetime as dt,hashlib,json,os,sys,time
from pathlib import Path
from zoneinfo import ZoneInfo
from cloud_publish_test import MCP,gh,read_file,change_file,profile,IG_USER,UTC
TZ=ZoneInfo('Asia/Yekaterinburg');ROOT=Path(__file__).resolve().parent.parent
def now():return dt.datetime.now(TZ)
def save_json(path,value,message):return change_file(path,lambda _:json.dumps(value,ensure_ascii=False,indent=2),message)
def queue():return json.loads(read_file('queue.json')[0])
def status(kind,**fields):
 fields.update(updated_at=now().isoformat(),run_url=os.environ.get('RUN_URL'))
 save_json('.cloud/'+kind+'.json',fields,'Update '+kind+' state')
def connection():
 key=os.environ.get('COMPOSIO_CONSUMER_KEY','')
 if not key.startswith('ck_'):raise RuntimeError('Add the Composio Connect ck_ key as the GitHub Actions secret COMPOSIO_CONSUMER_KEY. The expired test token is not used.')
 m=MCP(key,consumer=True)
 r=m.request('tools/call',{'name':'COMPOSIO_SEARCH_TOOLS','arguments':{'session':{'generate_id':True},'queries':[{'use_case':'Publish one Instagram Reel, inspect recent media, and add a hashtag comment'}]}})['result']
 body=json.loads(next(c['text'] for c in r['content'] if c.get('type')=='text'))
 m.tool_session=body['data']['session']['id'];profile(m)
 return m
def recent(m):return m.tool('INSTAGRAM_GET_IG_USER_MEDIA',{'ig_user_id':'me','limit':25,'fields':'id,caption,permalink,timestamp'}).get('data',[])
def finish(entry,media):
 day=dt.datetime.fromisoformat(media['timestamp'].replace('Z','+00:00')).astimezone(TZ).date().isoformat()
 save_json('.cloud/publications/'+day+'.json',dict(status='published',reel_id=entry['id'],media_id=media['id'],permalink=media['permalink'],published_at=media['timestamp']),'Confirm published Instagram media')
 def update(old):
  q=json.loads(old);e=next(v for v in q if v['id']==entry['id'])
  e.update(status='published',media_id=media['id'],permalink=media['permalink'],published_date=day)
  return json.dumps(q,ensure_ascii=False,indent=2)
 change_file('queue.json',update,'Record published '+entry['id'])
 line='\n- '+day+' — облачная публикация '+entry['id']+': '+media['permalink']+'\n'
 change_file('journal.md',lambda s:s if media['id'] in (s or '') else (s or '')+line+'  media_id='+media['id']+'\n','Log daily cloud publication')
 status('publisher',status='published',reel_id=entry['id'],permalink=media['permalink'])
def audit():
 q=queue();ready=[{'id':e['id'],'date':e['date'],'title':e.get('title',e['id'])} for e in q if e.get('status')=='ready']
 if os.environ.get('COMPOSIO_CONSUMER_KEY'):
  connection();auth='verified'
 else:auth='needs_COMPOSIO_CONSUMER_KEY'
 status('publisher',status='ready' if auth=='verified' else 'needs_auth',authentication=auth,time_zone='Asia/Yekaterinburg',daily_time='20:40',ready_queue=ready)
 print(json.dumps({'authentication':auth,'ready_queue':ready},ensure_ascii=False))
 if auth!='verified':raise RuntimeError('Persistent cloud publishing is waiting for COMPOSIO_CONSUMER_KEY')
def publish():
 m=connection();day=now().date().isoformat();media=recent(m)
 if any(dt.datetime.fromisoformat(v['timestamp'].replace('Z','+00:00')).astimezone(TZ).date().isoformat()==day for v in media):
  status('publisher',status='skipped_already_posted_today',date=day);return
 if not (20*60+40<=now().hour*60+now().minute<=22*60+40):raise RuntimeError('Outside the daily publication window')
 candidates=sorted([e for e in queue() if e.get('status')=='ready' and e['date']<=day],key=lambda e:e['date'])
 if not candidates:raise RuntimeError('No ready video is due today; planned items are not published')
 e=candidates[0];caption=e['caption'].replace('\\n','\n');path='.cloud/publications/'+day+'.json'
 found=next((v for v in media if v.get('caption')==caption),None)
 if found:finish(e,found);return
 old,_=read_file(path);state=json.loads(old) if old else {}
 if state.get('status') in ('publishing','unknown','published'):raise RuntimeError('Existing publication attempt requires reconciliation; no blind retry')
 if state.get('status')=='created' and state.get('reel_id')==e['id']:cid=state['container_id']
 else:
  r=m.tool('INSTAGRAM_POST_IG_USER_MEDIA',{'ig_user_id':IG_USER,'media_type':'REELS','video_url':e['video_raw_url'],'caption':caption,'thumb_offset':e.get('thumb_offset',3000),'share_to_feed':True})
  cid=r['id'];save_json(path,dict(status='created',reel_id=e['id'],container_id=cid),'Record prepared media container')
 save_json(path,dict(status='publishing',reel_id=e['id'],container_id=cid),'Record single publish attempt')
 try:r=m.tool('INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH',{'ig_user_id':IG_USER,'creation_id':cid,'max_wait_seconds':150})
 except Exception:
  time.sleep(15);found=next((v for v in recent(m) if v.get('caption')==caption),None)
  if found:finish(e,found);return
  save_json(path,dict(status='unknown',reel_id=e['id'],container_id=cid),'Stop after uncertain publication response')
  raise RuntimeError('Uncertain publication result. Verify Instagram before retrying.') from None
 media=m.tool('INSTAGRAM_GET_IG_MEDIA',{'ig_media_id':r['id'],'fields':'id,permalink,timestamp,caption'})
 finish(e,media)
 if e.get('hashtags'):
  try:m.tool('INSTAGRAM_POST_IG_MEDIA_COMMENTS',{'ig_media_id':media['id'],'message':e['hashtags']})
  except Exception:status('publisher',status='published_comment_unconfirmed',permalink=media['permalink'])
 print('Published',media['permalink'])
def next_slot(q,today,horizon=8):
 for i in range(1,horizon+1):
  day=today+dt.timedelta(days=i);entries=[e for e in q if e.get('date')==day.isoformat() and e.get('status') in ('ready','planned')]
  if any(e.get('status')=='ready' for e in entries):continue
  return day,next((e for e in entries if e.get('status')=='planned'),None)
 return None,None
def generate():
 from cloud_render import render
 bank=json.loads((ROOT/'content-bank.json').read_text(encoding='utf-8'));made=[]
 for _ in range(int(os.environ.get('MAX_GENERATE','2'))):
  q=queue();day,planned=next_slot(q,now().date())
  if day is None:break
  used={e.get('source_topic') for e in q};lesson=day.weekday() in (2,6)
  candidates=[t for t in bank if t['key'] not in used and (t['format']=='lesson')==lesson]
  if planned:candidates=[t for t in candidates if t.get('reel_id')==planned['id']]
  if not candidates:raise RuntimeError('Reviewed topic bank needs replenishment for '+day.isoformat()+'. Published videos are never recycled.')
  topic=candidates[0];rid=planned['id'] if planned else 'auto-'+day.isoformat()+'-'+topic['key']
  work=ROOT/'build'/rid;video,checks=render(topic,work)
  upload_path='reels/'+rid+'.mp4';raw=video.read_bytes();sha256=hashlib.sha256(raw).hexdigest()
  payload={'message':'Add rendered '+rid,'branch':'main','content':base64.b64encode(raw).decode()}
  existing=gh('contents/'+upload_path+'?ref=main')
  if existing:payload['sha']=existing['sha']
  gh('contents/'+upload_path,'PUT',payload)
  spec=dict(topic,validation=checks,sha256=sha256)
  save_json('specs/'+rid+'.json',spec,'Save validated teaching spec '+rid)
  change_file('lessons/'+rid+'-formulas.txt',lambda _:topic['title']+'\nGoogle Таблицы; русская локаль; английские имена функций.\n\n'+topic['formula']+'\n\n'+topic['caption'],'Save copyable formula '+rid)
  preview=work/'preview-00.jpg';pbytes=preview.read_bytes()
  pp='reels/'+rid+'-preview.jpg';old=gh('contents/'+pp+'?ref=main');payload={'message':'Save reel preview '+rid,'branch':'main','content':base64.b64encode(pbytes).decode()}
  if old:payload['sha']=old['sha']
  gh('contents/'+pp,'PUT',payload)
  entry=dict(id=rid,date=day.isoformat(),status='ready',format=topic['format'],title=topic['title'],source_topic=topic['key'],video=upload_path,video_raw_url='https://raw.githubusercontent.com/sts89279308855-web/ig-goog-lesheets/main/'+upload_path,caption=topic['caption'],hashtags=topic['hashtags'],thumb_offset=3000,validation=checks,sha256=sha256)
  def update(old):
   current=json.loads(old)
   if any(x.get('status')=='published' and x['id']==rid for x in current):raise RuntimeError('Queue entry was published during rendering')
   for i,x in enumerate(current):
    if x['id']==rid:current[i]={**x,**entry};break
   else:
    if any(x.get('date')==day.isoformat() and x.get('status') in ('ready','planned') for x in current):raise RuntimeError('The publication slot changed during rendering')
    current.append(entry)
   return json.dumps(current,ensure_ascii=False,indent=2)
  change_file('queue.json',update,'Queue verified video '+rid);made.append(rid)
  status('generator',status='running',generated=made,stock_days=8)
 status('generator',status='up_to_date' if not made else 'generated',generated=made,stock_days=8,remaining_topics=len(bank)-len({e.get('source_topic') for e in queue() if e.get('source_topic')}))
 print('Prepared',made)
def self_test():
 assert next_slot([{'date':'2026-10-31','status':'ready'}],dt.date(2026,10,30))[0]==dt.date(2026,11,1)
 assert next_slot([{'id':'l','date':'2026-10-31','status':'planned'}],dt.date(2026,10,30))[1]['id']=='l'
 bank=json.loads((ROOT/'content-bank.json').read_text(encoding='utf-8'));assert len({t['key'] for t in bank})==len(bank)
 for t in bank:
  assert len(t['caption'])<=2200 and len(t['hashtags'].split())<=4
  for i,s in enumerate(t['scenes']):
   from cloud_render import frame
   frame(s,i,len(t['scenes']),0);frame(s,i,len(t['scenes']),1)
 print('Self-tests passed for',len(bank),'topics')
if __name__=='__main__':
 mode=sys.argv[1]
 try:{'audit':audit,'publish':publish,'generate':generate,'self-test':self_test}[mode]()
 except Exception as e:
  print(type(e).__name__+': '+str(e))
  try:status('generator' if mode=='generate' else 'publisher',status='failed',message=str(e))
  except Exception:pass
  raise SystemExit(1)
