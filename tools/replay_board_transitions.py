"""Real-image-derived transition/degradation replay. No Windows simulation claim."""
import argparse,json,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.community_cards import read_board
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);args=p.parse_args()
row=json.loads(Path('docs/table-reading/development-labels.json').read_text())['tables'][7]
data=(args.assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);x,y,w,h=row['box'];crop=im[y:y+h,x:x+w]
expected=['Jc','5d','3c']
empty=crop.copy();empty[round(h*.35):round(h*.50),round(w*.17):round(w*.85)]=(160,65,30)
partial=crop.copy();partial[383:478,189:254]=(160,65,30)
hidden_rank=crop.copy();hidden_rank[386:420,123:150]=(30,160,30)
variants=[('original',crop,True),('empty',empty,False),('middle_card_hidden',partial,False),
 ('recovered',crop,True),('dim_70_percent',np.uint8(crop.astype(float)*.7),None),
 ('blurred',cv2.GaussianBlur(crop,(5,5),1.2),None),('rank_obstructed',hidden_rank,False),('recovered_again',crop,True)]
results=[]
for name,image,required in variants:
 r=read_board(image)
 accepted=r['status']=='EXPERIMENTAL_BOARD'
 outcome='correct' if accepted and r['cards']==expected else 'wrong' if accepted else 'abstained'
 results.append(dict(case=name,outcome=outcome,required_accept=required,result=r))
 print(name,outcome,r['cards'],r['status'],flush=True)
Path('docs/table-reading/board-transition-results.json').write_text(json.dumps(dict(scope='Eight sequential calls on one reused real flop and artificial transformations. Not eight real hands.',results=results),indent=2))
assert all(r['outcome']!='wrong' for r in results),'Wrong accepted board'
assert all(r['outcome']=='correct' for r in results if r['required_accept'] is True)
assert all(r['outcome']=='abstained' for r in results if r['required_accept'] is False)
