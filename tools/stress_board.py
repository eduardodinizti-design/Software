"""Scale/translation checks on one reused real flop; no generalization claim."""
import sys,json,hashlib,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.community_cards import read_board
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);args=p.parse_args()
row=json.loads(Path('docs/table-reading/development-labels.json').read_text())['tables'][7]
data=(args.assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);x,y,w,h=row['box'];crop=im[y:y+h,x:x+w]
results=[]
for width in (450,575,750):
 resized=cv2.resize(crop,(width,round(h*width/w)))
 # Move to another canvas and take the current source-local crop.
 canvas=np.zeros((resized.shape[0]+100,width+200,3),np.uint8)
 canvas[50:50+resized.shape[0],100:100+width]=resized
 result=read_board(canvas[50:50+resized.shape[0],100:100+width])
 entry=dict(width=width,expected=['Jc','5d','3c'],result=result)
 results.append(entry);print(width,result['status'],result['cards'],flush=True)
Path('docs/table-reading/board-scale-results.json').write_text(json.dumps(results,indent=2))
