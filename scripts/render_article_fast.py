import os,subprocess
import imageio_ffmpeg
root=os.path.dirname(__file__);ff=imageio_ffmpeg.get_ffmpeg_exe()
lines=open(root+'/concat.txt').read().splitlines();items=[]
for i in range(0,len(lines)-1,2):items.append((lines[i][6:-1],float(lines[i+1][9:])))
clips=[]
for j,(image,dur) in enumerate(items):
 out=root+'/clip%02d.mp4'%j
 subprocess.run([ff,'-y','-threads','1','-filter_threads','1','-loop','1','-framerate','30','-i',image,'-t',str(dur),'-an','-c:v','libx264','-preset','ultrafast','-threads','1','-crf','20','-pix_fmt','yuv420p','-r','30',out],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 clips.append(out);print('clip',j,flush=True)
open(root+'/clips.txt','w').write('\n'.join("file '"+c+"'" for c in clips))
subprocess.run([ff,'-y','-threads','1','-filter_threads','1','-f','concat','-safe','0','-i',root+'/clips.txt','-i',root+'/voice.wav','-c:v','copy','-c:a','aac','-b:a','160k','-ar','44100','-af','loudnorm=I=-16:TP=-1.5:LRA=11','-shortest','-movflags','+faststart',root+'/article-reel.mp4'],check=True,stdout=subprocess.DEVNULL,stderr=open(root+'/mux.log','w'))
open(root+'/done','w').write('ok');print('DONE',flush=True)
