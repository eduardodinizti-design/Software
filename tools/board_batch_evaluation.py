"""Batch real colored-board transformations; reuses development images."""
import argparse,hashlib,json,sys,time,os
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.community_cards import read_board
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
rows=json.loads(Path('docs/table-reading/colored-board-expansion.json').read_text())
cases=[]
for index,row in enumerate(rows):
 data=(a.assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
 image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);x,y,w,h=row['box'];crop=image[y:y+h,x:x+w]
 for width in (575,702,835):
  cases.append((f'{index}:width-{width}',cv2.resize(crop,(width,round(h*width/w))),row['expected'],row['source']))
 cases.append((f'{index}:dim70',np.uint8(crop.astype(float)*.7),row['expected'],row['source']))
 if len(row['expected'])==5:
  for pos in (0,1,2):
   altered=crop.copy();cx,cy,cw,ch=row['result']['candidates'][pos]
   altered[cy-2:cy+ch+2,cx-2:cx+cw+2]=(160,65,30)
   cases.append((f'{index}:occluded-card-{pos}',altered,None,row['source']))
def evaluate(case):
 name,image,expected,source=case;started=time.monotonic();result=read_board(image)
 accepted=result['status']=='EXPERIMENTAL_BOARD'
 outcome=('correct' if result['cards']==expected else 'wrong') if accepted else 'abstained'
 return dict(case=name,source=source,expected=expected,outcome=outcome,duration_ms=round((time.monotonic()-started)*1000,1),result=result)
with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(evaluate,cases))
summary={key:sum(r['outcome']==key for r in results) for key in ('correct','wrong','abstained')}
report=dict(scope='23 transformed cases from five reused development crops, not 23 independent hands. Timings collected concurrently, not latency benchmark.',summary=summary,results=results)
a.output.write_text(json.dumps(report,indent=2));print(summary)
for r in results:
 if r['outcome']!='correct':print(r['case'],r['outcome'],r['result']['cards'])

if summary['wrong']:
 raise SystemExit('Accepted incorrect board(s); inspect report')
