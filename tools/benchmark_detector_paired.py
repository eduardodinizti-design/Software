"""Same-process alternating detector-only benchmark; synthetic six-table frame."""
import argparse,importlib,json,sys,types,time,statistics
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from table_reading.automatic_table_crops import detect_table_crops
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
pkg=types.ModuleType('old_detector');pkg.__path__=[str(a.baseline/'table_reading')];sys.modules[pkg.__name__]=pkg
old=importlib.import_module('old_detector.automatic_table_crops').detect_table_crops
cv2.setNumThreads(1)
labels=json.loads((ROOT/'docs/table-reading/development-labels.json').read_text())['tables'];crops=[]
for i in (0,1,2,3,4,7):
 r=labels[i];im=cv2.imread(str(a.assets/r['source']));x,y,w,h=r['box'];crops.append(im[y:y+h,x:x+w])
cw=max(c.shape[1]for c in crops);ch=max(c.shape[0]for c in crops);pad=30
frame=np.zeros((2*(ch+pad)+pad,3*(cw+pad)+pad,3),np.uint8)
for i,c in enumerate(crops):
 x=pad+i%3*(cw+pad);y=pad+i//3*(ch+pad);frame[y:y+c.shape[0],x:x+c.shape[1]]=c
frame=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
reference=[r.to_dict()for r in old(frame)];assert reference==[r.to_dict()for r in detect_table_crops(frame)]
results=[]
for pair in range(10):
 for name,fn in ([('before',old),('after',detect_table_crops)]if pair%2==0 else [('after',detect_table_crops),('before',old)]):
  start=time.perf_counter();out=fn(frame);elapsed=(time.perf_counter()-start)*1000
  assert [r.to_dict()for r in out]==reference
  results.append(dict(pair=pair,mode=name,ms=elapsed))
summary={name:dict(n=10,median_ms=statistics.median([r['ms']for r in results if r['mode']==name]))for name in ('before','after')}
report=dict(scope='Same-process alternating ten warm pairs, OpenCV one thread, no OCR/capture. Six tiled reused crops are synthetic; not live Windows capacity.',candidate_parity=True,summary=summary,results=results)
a.output.write_text(json.dumps(report,indent=2));print(json.dumps(summary))
