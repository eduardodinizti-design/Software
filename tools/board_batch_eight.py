"""Replay manually labeled colored 8h board; table detection is bypassed."""
import os
os.environ.setdefault('OMP_THREAD_LIMIT','1')
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.community_cards import read_board
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
source='_8C143E80-F85C-4DE6-ADCD-0641771AE2E6__2a4e7ea0.png'
data=(a.assets/source).read_bytes();im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
x,y,w,h=703,54,703,1237;crop=im[y:y+h,x:x+w];expected=['2s','8h','5h']
results=[]
for width in (575,703,835):
 result=read_board(cv2.resize(crop,(width,round(h*width/w))))
 results.append(dict(width=width,expected=expected,matched=result['cards']==expected,result=result))
a.output.write_text(json.dumps(dict(source=source,sha256=hashlib.sha256(data).hexdigest(),box=[x,y,w,h],scope='One manually cropped real development hand, three resizes; detector bypassed.',results=results),indent=2))
print([(r['width'],r['matched'],r['result']['cards']) for r in results])

if not all(r['matched'] for r in results):
 raise SystemExit('Colored eight board regression')
