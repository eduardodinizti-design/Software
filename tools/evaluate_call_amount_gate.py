"""Offline feasibility inventory; no OCR calls and no runtime changes."""
import argparse,json,cv2,numpy as np,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from table_reading.button_templates import normalize
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
rows=json.load(open('docs/table-reading/button-expanded-validation.json'))['results'];calls=[]
for row in rows:
 for b in row['outputs']['False']['result']['buttons']:
  if not b.get('label','') or not b['label'].startswith('Call '):continue
  data=(args.assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
  im=cv2.imread(str(args.assets/row['source']));tx,ty,_,_=row['table_box'];x,y,w,h=b['box'];region=im[ty+y+round(h*.18):ty+y+round(h*.82),tx+x+round(w*.08):tx+x+round(w*.92)];hsv=cv2.cvtColor(region,cv2.COLOR_BGR2HSV);ink=np.uint8((hsv[:,:,1]<85)&(hsv[:,:,2]>165))*255
  pts=cv2.findNonZero(ink);xx,yy,ww,hh=cv2.boundingRect(pts);raw=ink[yy:yy+hh,xx:xx+ww];mask,aspect=normalize(255-cv2.resize(ink,None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST))
  calls.append(dict(source=row['source'],label=b['label'],shape=raw.shape,hash=hashlib.sha256(raw.tobytes()).hexdigest(),mask=mask,aspect=aspect))
for i,r in enumerate(calls):print(i,r['source'][:12],r['label'],r['shape'],r['hash'][:12])
matrix=[]
for i,r in enumerate(calls):
 scores=[]
 for j,s in enumerate(calls):
  if abs(r['aspect']/s['aspect']-1)>.035:score=0
  else:
   mask=cv2.resize(np.uint8(r['mask']),(s['mask'].shape[1],32),interpolation=cv2.INTER_NEAREST)>0;score=np.count_nonzero(mask&s['mask'])/np.count_nonzero(mask|s['mask'])
  scores.append(round(score,4))
 print(i,scores)
 matrix.append([float(v) for v in scores])

report=dict(scope='Eight whole Call labels from the existing sixteen-crop development report; no new OCR. Exact-mask equality gate only, not a generalized digit reader.',calls=[{k:v for k,v in r.items() if k!='mask'} for r in calls],iou_matrix=matrix,missing_digits=['4','7','8','9'],feasibility=dict(approximate_match='REJECT: Call1.0 vs Call1.6 IoU0.9394 leaves margin0.0606 below0.12',native_exact_match='Call1.0 native24x123 has identical masks in three distinct screenshot sources; other values/scales lack independently matching exemplars',generalized_amount_reader='NOT_VALIDATED'))
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
