"""Artificial turns from one labeled real river; never count as real turn evidence."""
import argparse,json,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.community_cards import read_board
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);args=p.parse_args()
docs=Path(__file__).resolve().parents[1]/'docs/table-reading'
row=next(r for r in json.loads((docs/'colored-board-expansion.json').read_text()) if len(r['expected'])==5)
data=(args.assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);x,y,w,h=row['box'];crop=im[y:y+h,x:x+w]
boxes=row['result']['candidates'];fx,fy,fw,fh=boxes[-1]
turn=crop.copy()
# Inpaint is NOT used: explicitly replace the fifth face with a nearby felt patch.
turn[fy-2:fy+fh+2,fx-2:fx+fw+2]=crop[fy-fh-12:fy-8,fx-2:fx+fw+2]
results=[]
for width in (575,702,835):
 resized=cv2.resize(turn,(width,round(h*width/w)))
 r=read_board(resized)
 results.append(dict(case='ARTIFICIAL_TURN',width=width,expected=row['expected'][:4],result=r))
 print(width,r['status'],r['street'],r['cards'],flush=True)
partial=crop.copy();partial[fy+fh//2:fy+fh+2,fx-2:fx+fw+2]=(160,65,30)
r=read_board(partial);results.append(dict(case='PARTIAL_FIFTH_FACE',expected_status='BOARD_PARTIAL_OR_OBSTRUCTED',result=r));print('partial',r['status'],r['cards'],flush=True)
(docs/'turn-variants.json').write_text(json.dumps(dict(source=row['source'],sha256=row['sha256'],scope='Artificial transformations of one real river. No real turn captured.',results=results),indent=2))
assert all(r['result']['cards']==r['expected'] and r['result']['street']=='TURN' for r in results if r['case']=='ARTIFICIAL_TURN')
assert results[-1]['result']['status']=='BOARD_PARTIAL_OR_OBSTRUCTED'
