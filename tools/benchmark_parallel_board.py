import sys,os,json,time,hashlib,statistics,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if len(sys.argv)>1:
 sys.path.insert(0,str(root))
 import cv2
 from table_reading.pipeline import analyze_tables
 labels=json.loads((root/'docs/table-reading/development-labels.json').read_text())['tables']
 result=[]
 def stable(x):
  if isinstance(x,dict):return {k:stable(v) for k,v in x.items() if k not in {'snapshot_id','snapshot_table_id','duration_ms','timings_ms','ocr_work'}}
  if isinstance(x,list):return [stable(v) for v in x]
  return x
 for i in (0,7):
  row=labels[i];im=cv2.imread(str(root/'public/assets/aistudio'/row['source']));x,y,w,h=row['box'];frame=im
  meta=dict(status='SUCCESS',image_shape=list(frame.shape),screen_origin=[0,0],hwnd=1,pid=1,process_created=0,executable='offline-probe')
  for n in range(3):
   start=time.perf_counter();r=analyze_tables(frame,meta,read_buttons=True,read_community=True);elapsed=(time.perf_counter()-start)*1000
   result.append(dict(source=row['source'],sample=n,ms=elapsed,ocr_calls=r.get('ocr_work',{}).get('calls'),tables=r['complete_count'],signature=hashlib.sha256(json.dumps(stable(r),sort_keys=True).encode()).hexdigest()))
 print(json.dumps(result));sys.exit()
all=[]
for mode in ('serial','parallel','parallel','serial'):
 env=dict(os.environ);env['VISUALPILOT_PARALLEL_BOARD']='1' if mode=='parallel' else '0'
 r=json.loads(subprocess.check_output([sys.executable,__file__,'child'],env=env,text=True));all.append(dict(mode=mode,samples=r));print(mode,round(statistics.median(x['ms'] for x in r)),flush=True)
(root/'docs/table-reading/parallel-board/pipeline-measurements.json').write_text(json.dumps(all,indent=2))
print('matching',all[0]['samples'][0]['signature']==all[1]['samples'][0]['signature'])
