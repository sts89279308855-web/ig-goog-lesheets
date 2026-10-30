import os,sys,json,subprocess
sys.path.insert(0,os.path.dirname(__file__))
import article_render as A
from PIL import Image
root=os.path.dirname(__file__)
scenes=json.load(open(root+'/scenes.json'))
keys={'hook':[(0.12,.8),(.38,1.5),(.5,4)],'solution':[(.2,.5),(.2,1.3),(.6,4)],'logic':[(.3,.5),(.3,2),(.4,5)],'change':[(.35,1),(.65,4)]}
concat=[];sheet=Image.new('RGB',(1080,960),'white');n=0
for i,s in enumerate(scenes):
 for fraction,t in keys.get(s['kind'],[(1,4)]):
  im=A.frame(s,t,i);path=root+'/key%02d.jpg'%n;im.save(path,quality=96,subsampling=0)
  concat.extend(["file '"+path+"'",'duration '+str(s['dur']*fraction)]);n+=1
 thumb=A.frame(s,5,i).resize((270,480));sheet.paste(thumb,((i%4)*270,(i//4)*480))
sheet.save(root+'/preview.jpg',quality=96)
A.frame(scenes[2],5,2).save(root+'/cover.jpg',quality=96)
concat.append("file '"+path+"'")
open(root+'/concat.txt','w').write('\n'.join(concat))
subprocess.run([sys.executable,root+'/render_article_fast.py'],check=True)
