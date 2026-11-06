"""Labeled real colored Hero crops plus explicit scale variants; batch replay."""
import argparse,concurrent.futures,hashlib,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
import cv2
from table_reading.inspect_cards import inspect
LABELS={1:['Qd','4h'],2:['Ah','Ks'],3:['Qd','Qs'],4:['Tc','Js'],5:['Tc','5c'],7:['3h','Qd'],8:['2h','Qc'],9:['Jd','2d'],10:['9d','2s'],11:['Tc','5c'],12:['Ah','Ks'],13:['7c','6h'],14:['7c','6h'],15:['5h','Kc'],16:['Qs','6h'],17:['2d','Ks'],18:['Td','5d']}
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=2);args=p.parse_args()
root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'docs/table-reading/eight-search.json').read_text())['entries']
jobs=[]
for i,expected in LABELS.items():
 row=rows[i];data=(args.assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
 for scale in (1,.75,.5):jobs.append((i,row,expected,scale))
def run(job):
 i,row,expected,scale=job;x,y,w,h=row['box'];im=cv2.imread(str(args.assets/row['source']))[y:y+h,x:x+w]
 if scale!=1:im=cv2.resize(im,None,fx=scale,fy=scale)
 started=time.monotonic();r=inspect(im,(0,0,im.shape[1],im.shape[0]));got=[c.get('card_candidate') for c in r['hero_rank_candidates']]
 return dict(index=i,source=row['source'],sha256=row['sha256'],box=row['box'],scale=scale,expected=expected,got=got,report=r,duration_ms=round((time.monotonic()-started)*1000,1))
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
 for row in pool.map(run,jobs):
  results.append(row);print(row['index'],row['scale'],row['expected'],row['got'],flush=True)
summary={}
for scale in (1,.75,.5):
 counts=dict(correct=0,wrong=0,unknown=0,ocr_errors=0)
 for row in results:
  if row['scale']!=scale:continue
  counts['ocr_errors'] += sum(c.get('status') == 'OCR_ERROR' for c in row['report']['hero_rank_candidates'])
  for got,want in zip(row['got'],row['expected']):counts['unknown' if got is None else 'correct' if got==want else 'wrong']+=1
 summary[str(scale)]=counts
args.output.write_text(json.dumps(dict(omp_thread_limit=os.environ.get('OMP_THREAD_LIMIT'),workers=args.workers,scope='17 visually labeled colored Hero regions from existing development screenshots; scales are transformations, not independent samples. Includes dark/folded examples. No colored eight present.',summary=summary,results=results),indent=2));print(summary)

if any(v["wrong"] for v in summary.values()) or summary["1"]["unknown"]:
 raise SystemExit("Hero regression: incorrect accepted card or unknown original")
