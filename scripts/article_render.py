
import os,sys,json,math,subprocess,textwrap
from PIL import Image,ImageDraw
sys.path.insert(0,os.path.dirname(__file__))
import reelgen as R
ROOT=os.path.dirname(__file__);W,H=1080,1920;FPS=12
BG='#F7F8F4';INK='#202823';MUT='#67716B';GREEN='#20764F';GL='#E4EFE5';RED='#BC4C45';RL='#F9E9E5';LINE='#D7DFD6'
def f(n,mono=False): return R.font(n,'Bold' if mono else 'ExtraBold',mono)
def txt(d,s,y,size=64,fill=INK,maxw=900,center=True):
 lines=[]
 for para in s.split('\n'):
  line=''
  for word in para.split():
   cand=(line+' '+word).strip()
   if d.textlength(cand,font=f(size))>maxw and line:lines.append(line);line=word
   else:line=cand
  lines.append(line)
 for i,line in enumerate(lines):
  x=(W-d.textlength(line,font=f(size)))/2 if center else 90
  d.text((x,y+i*size*1.22),line,font=f(size),fill=fill)
 return y+len(lines)*size*1.22
def label(d,s,y,fill=GREEN):txt(d,s,y,32,fill)
def box(d,b,fill='white',outline=None): d.rounded_rectangle(b,24,fill=fill,outline=outline,width=2)
def wrap_words(s,n=20):
 out=[];s=' '.join(s.split())
 while len(s)>n:
  cut=s.rfind(' ',0,n+1)
  if cut<=0:cut=n
  out.append(s[:cut]);s=s[cut:].lstrip()
 if s:out.append(s)
 return out
source='Поставка оборудования для новой кофейни'
good=wrap_words(source)
bad=[source[i:i+20] for i in range(0,len(source),20)]
assert good==['Поставка','оборудования для','новой кофейни']
def grid(d,lines,y=660,colour=GREEN,appear=999):
 cw=44;ch=94;x0=100
 nseen=0
 for ri in range(3):
  line=lines[ri] if ri<len(lines) else ''
  for ci in range(20):
   x=x0+ci*cw;yy=y+ri*126
   char=line[ci] if ci<len(line) and nseen<appear else ''
   bg=GL if char and colour==GREEN else RL if char else 'white'
   d.rounded_rectangle((x,yy,x+cw-3,yy+ch),7,fill=bg,outline=LINE,width=2)
   if char:
    font=f(31,True);tw=d.textlength(char,font=font)
    d.text((x+(cw-3-tw)/2,yy+27),char,font=font,fill=colour)
   if ci<len(line):nseen+=1
def entry(d,s,y=490):
 box(d,(90,y,990,y+130))
 txt(d,s,y+35,38,maxw=850)
def frame(scene,t,idx):
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
 for i in range(7):
  x=90+i*130
  d.rounded_rectangle((x,170,x+114,177),3,fill=GREEN if i<=idx else LINE)
 label(d,'EXCEL  /  РАЗБОР МОЕЙ СТАТЬИ',225)
 k=scene['kind']
 if k=='hook':
  txt(d,'По букве в клетку.\nА слово не влезло?',340,76)
  grid(d,bad,720,RED, int(t*19)+8)
  label(d,'20 клеток. Слово разорвано.',1160,RED)
 elif k=='problem':
  txt(d,'Формула работает.\nБланк — нет.',340,82)
  entry(d,source,590);grid(d,bad,800,RED)
  label(d,'Поставка оборудовани | я для…',1260,RED)
 elif k=='solution':
  txt(d,'Переносим\nслово целиком',340,86,GREEN)
  entry(d,source,590);grid(d,good,800,GREEN,int(max(0,t-0.4)*22))
  label(d,'Граница строки — последний пробел',1260)
 elif k=='logic':
  txt(d,'Не одна хитрость.\nТри понятных шага.',340,78)
  blocks=[('01','Найти пробел','до границы в 20 клеток'),('02','Взять остаток','после заполненной строки'),('03','Разложить буквы','ПСТР(текст;позиция;1)')]
  for j,(num,head,sub) in enumerate(blocks):
   yy=640+j*225;active=t>j*1.6
   box(d,(90,yy,990,yy+190),GL if active else 'white')
   d.text((125,yy+44),num,font=f(55,True),fill=GREEN if active else MUT)
   d.text((245,yy+35),head,font=f(47),fill=INK)
   d.text((245,yy+103),sub,font=f(31,True) if j==2 else f(34),fill=MUT)
 elif k=='change':
  txt(d,'Одна запись —\nготовый бланк',340,84,GREEN)
  s=source if t<1.8 else 'Доставка товаров для магазина'
  entry(d,s,590);grid(d,wrap_words(s),800,GREEN,999)
  label(d,'Без ручного переноса букв',1260)
 elif k=='expert':
  txt(d,'Удобная формула\nучитывает\nправила бланка',420,88)
  box(d,(120,1000,960,1250),GL)
  txt(d,'20 клеток в строке\nСлова остаются целыми',1055,49,GREEN,maxw=800)
 else:
  txt(d,'Есть такой\nбланк в Excel?',400,91)
  box(d,(130,870,950,1090),GREEN)
  txt(d,'Напишите «БЛАНК»',937,62,'white')
  txt(d,'Посмотрю задачу\nи предложу подход',1190,47,MUT)
 label(d,'@goog.lesheets',1570,MUT)
 return im
if __name__=='__main__':
 scenes=json.load(open(ROOT+'/scenes.json'));ff=R.imageio_ffmpeg.get_ffmpeg_exe()
 fd=ROOT+'/frames';os.makedirs(fd,exist_ok=True);k=0
 from PIL import ImageOps
 sheet=Image.new('RGB',(1080,960),'white')
 for idx,s in enumerate(scenes):
  for fi in range(round(s['dur']*FPS)):
   im=frame(s,fi/FPS,idx);im.save(f'{fd}/{k:05d}.jpg',quality=94,subsampling=0);k+=1
  th=frame(s,min(s['dur']-.5,4),idx).resize((270,480))
  sheet.paste(th,((idx%4)*270,(idx//4)*480))
 sheet.save(ROOT+'/preview.jpg',quality=95)
 frame(scenes[2],4,2).save(ROOT+'/cover.jpg',quality=95)
 out=ROOT+'/article-reel.mp4'
 p=subprocess.run([ff,'-y','-framerate',str(FPS),'-i',fd+'/%05d.jpg','-i',ROOT+'/voice.wav','-t',str(k/FPS),'-vf','fps=30','-c:v','libx264','-preset','veryfast','-crf','19','-threads','1','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-af','loudnorm=I=-16:TP=-1.5:LRA=11','-movflags','+faststart',out],stderr=open(ROOT+'/render.log','w'))
 if p.returncode:raise RuntimeError('render failed')
 open(ROOT+'/done','w').write(str(k/FPS))
 print('DONE',k/FPS)
