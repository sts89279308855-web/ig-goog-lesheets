"""Render reviewed teaching templates; fail closed on layout/audio errors."""
import array, functools, json, math, os, subprocess, time, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
try:
 import imageio_ffmpeg
 FF=imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
 import shutil
 FF=shutil.which('ffmpeg')
W,H,FPS=720,1280,24
ROOT=Path(__file__).resolve().parent.parent
@functools.lru_cache(None)
def font(size,mono=False):
 candidates=([r'C:/Windows/Fonts/consola.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'] if mono else [r'C:/Windows/Fonts/seguisb.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
 return ImageFont.truetype(next(p for p in candidates if Path(p).exists()),size)
def lines(text,size,width=624,mono=False):
 out=[];d=ImageDraw.Draw(Image.new('RGB',(1,1)))
 for para in text.split('\n'):
  current=''
  for word in para.split():
   trial=(current+' '+word).strip()
   if d.textlength(word,font=font(size,mono))>width:raise ValueError('Word does not fit the frame')
   if d.textlength(trial,font=font(size,mono))>width:out.append(current);current=word
   else:current=trial
  out.append(current)
 return out
def block(d,text,y,size=30,width=624,color='#172334',mono=False,x=48):
 for line in lines(text,size,width,mono):
  if y+size>1100:raise ValueError('Text outside the safe area')
  d.text((x,y),line,font=font(size,mono),fill=color);y+=size*1.3
 return y
def frame(scene,index,total,progress=1):
 im=Image.new('RGB',(W,H),'#F2F3F7');d=ImageDraw.Draw(im)
 d.rounded_rectangle((40,90,378,135),18,fill='#E6EEFC')
 d.text((54,99),'GOOGLE ТАБЛИЦЫ',font=font(23),fill='#176CE5')
 d.text((592,103),f'{index+1:02}/{total:02}',font=font(22),fill='#657182')
 y=block(d,scene['title'],185,40)
 y=block(d,scene.get('body',''),y+28,27,color='#657182')+30
 if scene.get('rows'):
  rows=[scene['cols']]+scene['rows'];n=len(scene['cols']);cw=624/n
  for ri,row in enumerate(rows):
   height=56
   for ci,value in enumerate(row):
    x=48+ci*cw;yy=y+ri*height
    d.rectangle((x,yy,x+cw,yy+height),fill='#E5F2E9' if ri==len(rows)-1 and progress>.6 else 'white',outline='#CCD4DE')
    fitted=lines(str(value),21,cw-20)
    if len(fitted)>2:raise ValueError('Table cell text is too long')
    for li,t in enumerate(fitted):d.text((x+9,yy+7+li*23),t,font=font(21),fill='#172334')
  y+=len(rows)*56+30
 if scene.get('code'):
  code=scene['code'];height=40*len(code)+35
  if y+height>1080:raise ValueError('Formula outside safe area')
  d.rounded_rectangle((40,y,680,y+height),18,fill='#182638')
  budget=int(sum(map(len,code))*min(1,progress*2.5))
  for ri,line in enumerate(code):
   if d.textlength(line,font=font(25,True))>600:raise ValueError('Formula line does not fit')
   visible=line[:max(0,budget)];budget-=len(line)
   d.text((55,y+16+ri*40),visible,font=font(25,True),fill='#F2F6FD')
 if scene.get('presenter'):
  sheet=Image.open(ROOT/'assets/author-presenter.jpg').convert('RGB')
  pose=sheet.crop((0,0,int(sheet.width*.55),sheet.height))
  pose=ImageOps.fit(pose,(340,430),centering=(.5,.4))
  im.paste(pose,(340,640));d=ImageDraw.Draw(im)
  block(d,'Разбираем\nпо шагам',665,34,width=260,color='#176CE5')
 d.text((230,1135),'@goog.lesheets',font=font(27),fill='#657182')
 d.rounded_rectangle((48,1180,672,1187),3,fill='#DCE2EA')
 d.rounded_rectangle((48,1180,48+max(1,int(624*(index+progress)/total)),1187),3,fill='#176CE5')
 return im
def render(topic,outdir):
 outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
 chunks=[];durations=[];scenes=topic['scenes'];lesson=topic['format']=='lesson'
 for i,s in enumerate(scenes):
  mp3=outdir/f'{i}.mp3'
  args=['edge-tts','--voice','ru-RU-SvetlanaNeural','--rate=+18%','--text',s['voice'],'--write-media',str(mp3)]
  for attempt in range(4):
   try:r=subprocess.run(args,capture_output=True,timeout=90)
   except subprocess.TimeoutExpired:r=None
   if r is not None and r.returncode==0 and mp3.exists() and mp3.stat().st_size>1000:break
   reason='timeout' if r is None else next((v for v in ['NoAudioReceived','403','429'] if v in r.stderr.decode(errors='replace')),'service_error')
   if attempt==3:raise RuntimeError('Speech synthesis failed at scene '+str(i+1)+': '+reason)
   print('Retrying speech scene',i+1,'after',reason,flush=True);time.sleep([3,10,25][attempt])
  time.sleep(1)
  raw=subprocess.run([FF,'-v','error','-i',str(mp3),'-f','s16le','-ac','2','-ar','44100','-'],check=True,capture_output=True).stdout
  samples=array.array('h',raw)
  if not samples or max(map(abs,samples[::100]))<200:raise ValueError('Speech is missing or silent')
  dur=max(6 if lesson else 4.5,len(raw)/176400+.6)
  dur=math.ceil(dur*FPS)/FPS;durations.append(dur)
  padding=max(0,round(dur*44100)*4-len(raw));chunks.append(raw+b'\0'*padding)
 if lesson and sum(durations)<60:
  extra=60-sum(durations);durations[-1]+=extra;chunks[-1]+=b'\0'*round(extra*176400)
 length=sum(durations)
 tempo=1.0
 if lesson and 90<length<=98.5:
  tempo=length/88
  durations=[round(d/tempo*FPS)/FPS for d in durations]
  length=sum(durations)
 if not (60<=length<=90 if lesson else 20<=length<=60):raise ValueError('Video duration outside teaching format: '+str(length))
 wav=outdir/'voice.wav'
 with wave.open(str(wav),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b''.join(chunks))
 if tempo>1:
  sped=outdir/'voice-paced.wav'
  subprocess.run([FF,'-v','error','-y','-i',str(wav),'-af','atempo='+str(tempo),str(sped)],check=True,capture_output=True)
  wav=sped
 out=outdir/'video.mp4';log=outdir/'ffmpeg.log'
 with log.open('w') as err:
  p=subprocess.Popen([FF,'-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s','720x1280','-r',str(FPS),'-i','-','-i',str(wav),'-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-threads','2','-c:a','aac','-b:a','128k','-movflags','+faststart','-shortest',str(out)],stdin=subprocess.PIPE,stderr=err)
  try:
   for i,(s,dur) in enumerate(zip(scenes,durations)):
    cache={}
    for fi in range(round(dur*FPS)):
     key=min(20,int(fi/(dur*FPS)*20));pr=key/20
     if key not in cache:cache[key]=frame(s,i,len(scenes),pr).tobytes()
     p.stdin.write(cache[key])
    frame(s,i,len(scenes),1).save(outdir/f'preview-{i:02}.jpg')
   p.stdin.close()
   if p.wait(timeout=120)!=0:raise ValueError('Video encoder failed')
  except BaseException:p.kill();p.wait();raise
 probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(out)],check=True,capture_output=True).stdout)
 streams=probe['streams'];v=next(x for x in streams if x['codec_type']=='video');a=next(x for x in streams if x['codec_type']=='audio')
 if (v['width'],v['height'])!=(720,1280) or abs(float(probe['format']['duration'])-length)>.3:raise ValueError('Video verification failed')
 if out.stat().st_size>90*1024*1024:raise ValueError('Video exceeds repository upload limit')
 check={'duration':round(length,2),'width':720,'height':1280,'audio':a['codec_name'],'layout_checks':'passed','voice':'ru-RU-SvetlanaNeural','speech_tempo':round(tempo,3),'synthetic_media_disclosed':True}
 (outdir/'validation.json').write_text(json.dumps(check,indent=2))
 return out,check
