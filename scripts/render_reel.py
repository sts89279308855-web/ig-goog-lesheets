
# python render_reel.py <scenes.json> <out.mp4> [voice.wav]  — пишет <out.mp4>.done по окончании
import sys, json, os, subprocess, shutil
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import reelgen as R
from PIL import Image
scenes=json.load(open(sys.argv[1])); out=sys.argv[2]
fd='/tmp/frames_'+os.path.basename(out); shutil.rmtree(fd,ignore_errors=True); os.makedirs(fd)
k=0
for si,s in enumerate(scenes):
    for fi in range(int(s['dur']*R.FPS)):
        t=fi/R.FPS
        img=Image.new('RGBA',(R.W,R.H),R.BG+(255,)); R.SCENES[s['type']](img,t,s)
        fade=min(1,(s['dur']-t)/0.18) if si<len(scenes)-1 else 1
        if fade<1: img=Image.blend(Image.new('RGBA',(R.W,R.H),R.BG+(255,)),img,max(0,fade))
        img.convert('RGB').save(f'{fd}/{k:05d}.png',compress_level=1); k+=1
exe=R.imageio_ffmpeg.get_ffmpeg_exe()
audio=['-i',sys.argv[3]] if len(sys.argv)>3 else ['-f','lavfi','-i','anullsrc=r=44100:cl=stereo']
subprocess.run([exe,'-y','-framerate',str(R.FPS),'-i',f'{fd}/%05d.png']+audio+['-t',str(k/R.FPS),
 '-c:v','libx264','-preset','veryfast','-threads','1','-x264-params','rc-lookahead=5:ref=1:bframes=0','-pix_fmt','yuv420p','-profile:v','high','-crf','21',
 '-c:a','aac','-b:a','128k','-movflags','+faststart',out],stderr=open(out+'.log','w'))
shutil.rmtree(fd,ignore_errors=True)
open(out+'.done','w').write('ok')
