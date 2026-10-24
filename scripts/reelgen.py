
import os, subprocess, math, urllib.request, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
W,H,FPS=1080,1920,30
FD=os.environ.get('IG_FONTS','/home/user/ig/fonts/')
FONT_URLS={'Manrope.ttf':'https://github.com/google/fonts/raw/main/ofl/manrope/Manrope%5Bwght%5D.ttf',
           'JetBrainsMono.ttf':'https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf'}
def ensure_fonts():
    os.makedirs(FD,exist_ok=True)
    for n,u in FONT_URLS.items():
        if not os.path.exists(FD+n): urllib.request.urlretrieve(u,FD+n)
BG=(250,250,247); INK=(28,28,30); MUTED=(110,110,115); GREEN=(24,128,56); GREENL=(230,244,234)
RED=(217,48,37); REDL=(252,232,230); LINE=(222,222,218); CARD=(255,255,255)
_fc={}
def font(size,w='Bold',mono=False):
    k=(size,w,mono)
    if k not in _fc:
        ensure_fonts()
        f=ImageFont.truetype(FD+('JetBrainsMono.ttf' if mono else 'Manrope.ttf'),size)
        try: f.set_variation_by_name(w)
        except Exception: pass
        _fc[k]=f
    return _fc[k]
def ease(t): t=max(0,min(1,t)); return 1-(1-t)**3
def wrap(d,text,f,maxw):
    out=[]
    for para in text.split('\n'):
        line=''
        for w in para.split(' '):
            t=(line+' '+w).strip()
            if d.textlength(t,font=f)<=maxw: line=t
            else: out.append(line); line=w
        out.append(line)
    return out
def text_block(d,img,text,size,y,t,color=INK,w='ExtraBold',maxw=900,lh=1.18,stagger=0.12,hl=None):
    f=font(size,w); lines=wrap(d,text,f,maxw)
    for i,l in enumerate(lines):
        p=ease((t-i*stagger)/0.35)
        if p<=0: continue
        lw=d.textlength(l,font=f); x=(W-lw)/2; yy=y+i*size*lh+(1-p)*40
        layer=Image.new('RGBA',(W,H),(0,0,0,0)); ld=ImageDraw.Draw(layer)
        c=color
        if hl and any(h in l for h in hl): c=GREEN
        ld.text((x,yy),l,font=f,fill=c+(int(255*p),))
        img.alpha_composite(layer)
    return y+len(lines)*size*lh
def footer(d):
    f=font(34,'SemiBold'); s='@goog.lesheets'
    d.text(((W-d.textlength(s,font=f))/2,1540),s,font=f,fill=MUTED)
def pill(d,x,y,text,fg,bg,size=34):
    f=font(size,'Bold'); tw=d.textlength(text,font=f)
    d.rounded_rectangle((x,y,x+tw+44,y+size+30),radius=(size+30)//2,fill=bg); d.text((x+22,y+12),text,font=f,fill=fg)
def scene_title(img,t,s):
    d=ImageDraw.Draw(img)
    if s.get('kicker'):
        p=ease(t/0.3); f=font(38,'Bold'); k=s['kicker']; kw=d.textlength(k,font=f)
        d.rounded_rectangle(((W-kw)/2-28,430,(W+kw)/2+28,500),radius=35,fill=GREENL); d.text(((W-kw)/2,442),k,font=f,fill=GREEN)
    text_block(d,img,s['text'],s.get('size',92),s.get('y',580),t-0.15,hl=s.get('hl'))
    if s.get('sub'): text_block(ImageDraw.Draw(img),img,s['sub'],46,s.get('suby',1180),t-0.6,color=MUTED,w='Medium',maxw=860)
    footer(ImageDraw.Draw(img))
def scene_table(img,t,s):
    d=ImageDraw.Draw(img)
    cols=s['cols']; rows=s['rows']; cw=s['cw']; x0=(W-sum(cw))//2; y0=s.get('y',470); rh=118
    if s.get('title'): text_block(d,img,s['title'],62,300,t)
    d=ImageDraw.Draw(img)
    d.rounded_rectangle((x0-10,y0-10,x0+sum(cw)+10,y0+rh*(len(rows)+1)+10),radius=28,fill=CARD,outline=LINE,width=3)
    x=x0; fh=font(34,'Bold')
    d.rounded_rectangle((x0-10,y0-10,x0+sum(cw)+10,y0+rh),radius=28,fill=(241,243,244))
    for i,c in enumerate(cols): d.text((x+24,y0+38),c,font=fh,fill=MUTED); x+=cw[i]
    fr=font(40,'SemiBold')
    hl_t=s.get('hl_at',99)
    green=s.get('hl_green')
    for r,row in enumerate(rows):
        rp=ease((t-0.3-r*0.18)/0.3)
        if rp<=0: continue
        yy=y0+rh*(r+1); x=x0
        flag=s.get('flags',[False]*len(rows))[r]; hp=ease((t-hl_t-r*0.12)/0.3) if flag else 0
        if hp>0:
            HB=GREENL if green else REDL
            d.rectangle((x0,yy,x0+sum(cw),yy+rh),fill=tuple(int(CARD[k]+(HB[k]-CARD[k])*hp) for k in range(3)))
        d.line((x0,yy,x0+sum(cw),yy),fill=LINE,width=2)
        for i,v in enumerate(row):
            if v=='__STATUS__':
                st=s['status'][r]; sp=ease((t-s.get('status_at',99)-r*0.12)/0.25)
                bad=flag and not green
                if sp>0: pill(d,x+18,yy+30,st, RED if bad else GREEN, REDL if bad else GREENL,size=30)
            else:
                col=(GREEN if green else RED) if (flag and hp>0.5 and i==s.get('hl_col',1)) else INK
                d.text((x+24,yy+36),str(v),font=fr,fill=col)
            x+=cw[i]
    if s.get('formula'):
        ft=s.get('formula_at',1.2); fp=(t-ft)/1.2
        if fp>0:
            txt=s['formula']; n=int(len(txt)*min(1,fp)); fy=y0+rh*(len(rows)+1)+90
            fm=font(40,'Bold',mono=True); tw=d.textlength(txt,font=fm,features=['-liga','-calt'])
            bx=(W-tw)/2-36
            d.rounded_rectangle((bx,fy,bx+tw+72,fy+110),radius=24,fill=INK)
            d.text((bx+36,fy+30),txt[:n]+('|' if fp<1 and int(t*4)%2==0 else ''),font=fm,fill=(255,255,255),features=['-liga','-calt'])
            if s.get('formula_note') and fp>1.1:
                text_block(ImageDraw.Draw(img),img,s['formula_note'],40,fy+150,t-ft-1.3,color=MUTED,w='Medium',maxw=880)
SCENES={'title':scene_title,'table':scene_table}
def still(scene,t,out):
    img=Image.new('RGBA',(W,H),BG+(255,)); SCENES[scene['type']](img,t,scene); img.convert('RGB').save(out,quality=92); return out
