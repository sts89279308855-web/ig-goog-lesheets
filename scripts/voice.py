
import sys, json, os, subprocess, time, wave
import numpy as np, imageio_ffmpeg
VOICE=os.environ.get('IG_VOICE','ru-RU-SvetlanaNeural'); RATE='+8%'; SR=44100; LEAD=0.15; TAIL=0.45
exe=imageio_ffmpeg.get_ffmpeg_exe()
def tts(text,mp3):
    for _ in range(4):
        subprocess.run(['edge-tts','--voice',VOICE,'--rate='+RATE,'--text',text,'--write-media',mp3],capture_output=True)
        if os.path.exists(mp3) and os.path.getsize(mp3)>0: return
        time.sleep(3)
    raise RuntimeError('edge-tts не вернул звук: '+text[:40])
def pcm(mp3):
    raw=subprocess.run([exe,'-v','quiet','-i',mp3,'-f','s16le','-ac','2','-ar',str(SR),'-'],capture_output=True).stdout
    return np.frombuffer(raw,dtype=np.int16).reshape(-1,2)
spec_path,out=sys.argv[1],sys.argv[2]
scenes=json.load(open(spec_path)); parts=[]
for i,s in enumerate(scenes):
    a=np.zeros((0,2),dtype=np.int16)
    if s.get('voice'):
        mp3=f'/tmp/voice_{os.getpid()}_{i}.mp3'; tts(s['voice'],mp3); a=pcm(mp3)
        s['dur']=round(max(s['dur'],LEAD+len(a)/SR+TAIL),2)
    n=int(int(s['dur']*30)/30*SR)
    seg=np.zeros((n,2),dtype=np.int16); st=int(LEAD*SR) if len(a) else 0
    seg[st:st+len(a)]=a[:max(0,n-st)]
    parts.append(seg)
track=np.concatenate(parts)
with wave.open(out,'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(track.tobytes())
json.dump(scenes,open(spec_path,'w'),ensure_ascii=False,indent=1)
print('ok',round(len(track)/SR,2))
