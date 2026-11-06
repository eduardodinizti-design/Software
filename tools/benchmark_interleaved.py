"""Alternating isolated reader processes: six diverse crops, no concurrent OCR."""
import argparse,json,os,subprocess,sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def worker(implementation,assets):
 os.environ['OMP_THREAD_LIMIT']='1';sys.path.insert(0,str(implementation))
 import cv2,numpy as np
 from table_reading.pipeline import analyze_tables
 cv2.setNumThreads(1)
 labels=json.loads((ROOT/'docs/table-reading/development-labels.json').read_text())['tables']
 rows=[labels[i] for i in (0,1,2,3,4,7)];crops=[]
 for row in rows:
  import hashlib
  data=(assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
  im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);x,y,w,h=row['box'];crops.append(im[y:y+h,x:x+w])
 cw=max(c.shape[1] for c in crops);ch=max(c.shape[0] for c in crops);pad=30
 frame=np.zeros((2*(ch+pad)+pad,3*(cw+pad)+pad,3),np.uint8)
 for i,c in enumerate(crops):
  x=pad+i%3*(cw+pad);y=pad+i//3*(ch+pad);frame[y:y+c.shape[0],x:x+c.shape[1]]=c
 meta=dict(status='SUCCESS',image_shape=list(frame.shape),screen_origin=[0,0],hwnd=1,pid=1,process_created=0,executable='offline-fixture')
 expected=[(r['expected'],['Jc','5d','3c'] if i==5 else []) for i,r in enumerate(rows)]
 for line in sys.stdin:
  start=time.perf_counter();r=analyze_tables(frame,meta,read_buttons=True,read_community=True);elapsed=(time.perf_counter()-start)*1000
  out=[]
  for t in r['tables']:
   b=t.get('board',{});buttons=t.get('action_buttons',{})
   out.append(dict(box=t['local_box'],status=t['status'],hero=t['hero_cards'],reading_status=t['reading_status'],board={k:b.get(k) for k in ('cards','street','status')},buttons=dict(status=buttons.get('status'),items=[{k:x.get(k) for k in ('action','label_action','amount','unit','kind','status')} for x in buttons.get('buttons',[])])))
  actual=[(t['hero_cards'],t.get('board',{}).get('cards',[])) for t in r['tables'] if t['status']=='COMPLETE_CANDIDATE']
  print(json.dumps(dict(wall_ms=elapsed,stages=r['timings_ms'],ocr_work=r['ocr_work'],semantic=out,expected_match=actual==expected)),flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--baseline',type=Path);p.add_argument('--output',type=Path);p.add_argument('--worker',type=Path);a=p.parse_args()
 if a.worker:return worker(a.worker,a.assets)
 if not a.baseline or not a.output:p.error('--baseline and --output required')
 children={};results=[]
 try:
  for name,path in [('before',a.baseline),('after',ROOT)]:
   children[name]=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',str(path),'--assets',str(a.assets)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
  reference=None
  for sample in range(6):
   for name in (('before','after') if sample%2==0 else ('after','before')):
    proc=children[name];proc.stdin.write('run\n');proc.stdin.flush();line=proc.stdout.readline()
    if not line:raise RuntimeError('Benchmark child stopped: '+name)
    row=json.loads(line);row.update(mode=name,sample=sample)
    if reference is None:reference=row['semantic']
    row['semantic_equal']=row['semantic']==reference;results.append(row)
    print(name,sample,round(row['wall_ms'],1),row['expected_match'],row['semantic_equal'],flush=True)
  import numpy as np
  summary={}
  for name in children:
   samples=[r for r in results if r['mode']==name and r['sample']>0]
   def stats(values):return dict(median_ms=round(statistics.median(values),2),p95_ms=round(float(np.percentile(values,95)),2))
   summary[name]=dict(wall=stats([r['wall_ms'] for r in samples]),stages={k:stats([r['stages'][k] for r in samples]) for k in samples[0]['stages']})
  passed=all(r['expected_match'] and r['semantic_equal'] for r in results)
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(scope='Six tiled reused development crops; isolated reader processes, alternating before/after order, never simultaneous OCR. First sample per mode excluded from summary; five samples per mode. Linux only, no capture, exploratory p95.',passed=passed,summary=summary,results=results),indent=2));return 0 if passed else 1
 finally:
  for proc in children.values():
   proc.stdin.close()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
if __name__=='__main__':raise SystemExit(main())
