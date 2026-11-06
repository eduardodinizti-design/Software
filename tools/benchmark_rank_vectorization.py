"""Paired rank-only benchmark: fixed real crops, no OCR, alternating order."""
import argparse,hashlib,importlib.util,json,statistics,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from table_reading import rank_templates as current
from table_reading.card_alignment import locate_card_pair
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--repetitions',type=int,default=20);args=p.parse_args()
spec=importlib.util.spec_from_file_location('rank_scalar_baseline',args.baseline);baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
root=Path(__file__).resolve().parents[1];rows=json.loads((root/'docs/table-reading/hero-batch-small-aspect.json').read_text())['results'];crops=[]
for row in rows:
 path=args.assets/row['source'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'];x,y,w,h=row['box'];im=cv2.imread(str(path))[y:y+h,x:x+w]
 if row['scale']!=1:im=cv2.resize(im,None,fx=row['scale'],fy=row['scale'])
 im=cv2.resize(im,(720,1280));dy=locate_card_pair(im)['vertical_offset']
 crops.extend(im[1010+dy:1070+dy,left:left+42].copy() for left in (402,447))
def run(reader):
 start=time.perf_counter_ns();results=[reader(crop) for crop in crops]
 return (time.perf_counter_ns()-start)/1e6,results
# Cold atlas loading, image I/O and crop construction are excluded. Both paths warm.
a,expected=run(baseline.read_template_rank);b,actual=run(current.read_template_rank);assert expected==actual
pairs=[]
for index in range(args.repetitions):
 order=('baseline','current') if index%2==0 else ('current','baseline');times={}
 for name in order:
  elapsed,result=run(baseline.read_template_rank if name=='baseline' else current.read_template_rank)
  assert result==expected,(index,name,'decision drift')
  times[name]=elapsed
 pairs.append(dict(repetition=index,order=list(order),**times,delta_ms=times['current']-times['baseline']))
summary={name:dict(median_batch_ms=statistics.median(r[name] for r in pairs),mean_batch_ms=statistics.mean(r[name] for r in pairs),median_per_crop_ms=statistics.median(r[name] for r in pairs)/len(crops)) for name in ('baseline','current')}
summary['paired_delta_median_ms']=statistics.median(r['delta_ms'] for r in pairs);summary['current_faster_pairs']=sum(r['delta_ms']<0 for r in pairs);summary['exact_parity']=True
report=dict(scope='Rank shortcut only, no OCR; 102 reused real development crops,20 alternating paired repetitions. Excludes cold loading and capture. Not Windows latency.',baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),current_sha256=hashlib.sha256(Path(current.__file__).read_bytes()).hexdigest(),crop_count=len(crops),repetitions=args.repetitions,summary=summary,pairs=pairs)
args.output.write_text(json.dumps(report,indent=2));print(json.dumps(summary,indent=2))
