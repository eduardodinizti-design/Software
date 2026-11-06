"""Compare template fast paths with the preserved, memoized OCR pipeline."""
import os
os.environ['OMP_THREAD_LIMIT']='1'
import argparse,hashlib,json,math,platform,statistics,sys,time
from pathlib import Path
sys.path.insert(0,os.environ.get('VISUALPILOT_READER_ROOT',str(Path(__file__).resolve().parents[1])))
import cv2,numpy as np
from table_reading.pipeline import analyze_tables
from table_reading.fastpath import template_mode
cv2.setNumThreads(1)
ROOT=Path(__file__).resolve().parents[1]

def summary(values):
 return dict(n=len(values),median_ms=round(statistics.median(values),2),p95_ms=round(float(np.percentile(values,95)),2))

def meaning(result):
 rows=[]
 for r in result['tables']:
  b=r.get('board',{});buttons=r.get('action_buttons',{})
  rows.append(dict(box=r['local_box'],status=r['status'],hero=r['hero_cards'],reading_status=r['reading_status'],
   board=dict(cards=b.get('cards'),status=b.get('status'),street=b.get('street')),
   buttons=dict(status=buttons.get('status'),items=[{k:x.get(k) for k in ('action','label_action','amount','unit','kind','status')} for x in buttons.get('buttons',[])])))
 return dict(rows=rows,actions_allowed=result['actions_allowed'])

def main():
 p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--samples',type=int,default=5);p.add_argument('--modes',choices=('both','templates'),default='both');a=p.parse_args()
 if a.samples<5:p.error('Use at least five warm samples')
 labels=json.loads((ROOT/'docs/table-reading/development-labels.json').read_text())['tables']
 labels=[dict(labels[i],board=['Jc','5d','3c'] if i==7 else []) for i in (0,1,2,3,4,7)]
 crops=[];sources={}
 for row in labels:
  data=(a.assets/row['source']).read_bytes();digest=hashlib.sha256(data).hexdigest();assert digest==row['sha256'];sources[row['source']]=digest
  im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);x,y,w,h=row['box'];crops.append(im[y:y+h,x:x+w])
 report=dict(scope='Linux offline synthetic tiled development crops; both modes use exact per-frame OCR memo. Not independent accuracy, Windows capture or live multi-table capacity. Five warm samples and first call separate; fixed baseline-first order may bias timings.',environment=dict(platform=platform.platform(),opencv=cv2.__version__,opencv_threads=1,OMP_THREAD_LIMIT=1),sources=sources,scenarios=[])
 errors=[];a.output.parent.mkdir(parents=True,exist_ok=True)
 for n in (1,3,6):
  cw=max(c.shape[1] for c in crops[:n]);ch=max(c.shape[0] for c in crops[:n]);cols=min(n,3);pad=30
  frame=np.zeros((math.ceil(n/cols)*(ch+pad)+pad,cols*(cw+pad)+pad,3),np.uint8)
  for i,c in enumerate(crops[:n]):
   x=pad+i%cols*(cw+pad);y=pad+i//cols*(ch+pad);frame[y:y+c.shape[0],x:x+c.shape[1]]=c
  meta=dict(status='SUCCESS',image_shape=list(frame.shape),screen_origin=[0,0],hwnd=1,pid=1,process_created=0,executable='offline-fixture')
  expected=sorted((tuple(r['expected']),tuple(r['board'])) for r in labels[:n]);entry=dict(tables=n,modes={});reference=None
  for enabled in ((False,True) if a.modes=='both' else (True,)):
   name='templates' if enabled else 'ocr';samples=[]
   for i in range(a.samples+1):
    start=time.perf_counter()
    with template_mode(enabled):r=analyze_tables(frame,meta,read_buttons=True,read_community=True)
    elapsed=(time.perf_counter()-start)*1000;m=meaning(r)
    if reference is None:reference=m
    actual=sorted((tuple(t['hero_cards']),tuple(t.get('board',{}).get('cards',[]))) for t in r['tables'] if t['status']=='COMPLETE_CANDIDATE')
    ok=m==reference and actual==expected
    if not ok:errors.append(dict(tables=n,mode=name,index=i,actual=actual,meaning=m,reference=reference))
    item=dict(wall_ms=elapsed,timings_ms=r['timings_ms'],ocr_work=r['ocr_work'],matched=ok)
    if i==0:entry['modes'][name]=dict(first_call=item,semantic=m)
    else:samples.append(item)
    print(n,name,i,round(elapsed,1),r['ocr_work'],'PASS' if ok else 'FAIL',flush=True)
   entry['modes'][name].update(samples=samples,wall=summary([x['wall_ms'] for x in samples]),stages={k:summary([x['timings_ms'][k] for x in samples]) for k in samples[0]['timings_ms']})
  report['scenarios'].append(entry);report['errors']=errors;a.output.write_text(json.dumps(report,indent=2))
 report['all_matched']=not errors;a.output.write_text(json.dumps(report,indent=2));return bool(errors)
if __name__=='__main__':raise SystemExit(main())
