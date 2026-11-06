"""Sequential offline pipeline benchmark; repeated and diverse real development crops."""
import os
os.environ['OMP_THREAD_LIMIT']='1'
import argparse,hashlib,json,math,platform,statistics,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.pipeline import analyze_tables
from table_reading.ocr_runtime import ocr_frame
cv2.setNumThreads(1)
ROOT=Path(__file__).resolve().parents[1]

def semantic(result):
    volatile={'snapshot_id','snapshot_table_id','duration_ms','timings_ms','ocr_work'}
    if isinstance(result,dict):return {k:semantic(v) for k,v in result.items() if k not in volatile}
    if isinstance(result,list):return [semantic(v) for v in result]
    return result

def stats(values):
    values=sorted(values)
    return dict(n=len(values),median=round(statistics.median(values),3),p95=round(float(np.percentile(values,95)),3))

def cpu_model():
    try:
        return next(line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name'))
    except (OSError,StopIteration):
        return platform.processor() or 'unknown'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--samples',type=int,default=5);a=p.parse_args()
    if a.samples<5:p.error('At least five warm samples required')
    labels=json.loads((ROOT/'docs/table-reading/development-labels.json').read_text())['tables']
    board=json.loads((ROOT/'docs/table-reading/colored-board-expansion.json').read_text())[0]
    repeated=dict(board,hero=['Ah','Ks'],board=['3d','Ad','3s'])
    diverse=[dict(labels[i],hero=labels[i]['expected'],board=['Jc','5d','3c'] if i==7 else []) for i in (0,1,2,3,4,7)]
    sources={}
    def crop(row):
        data=(a.assets/row['source']).read_bytes();digest=hashlib.sha256(data).hexdigest()
        assert digest==row['sha256'];sources[row['source']]=digest
        im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);x,y,w,h=row['box']
        return im[y:y+h,x:x+w].copy()
    def scene(rows):
        crops=[crop(row) for row in rows];cw=max(im.shape[1] for im in crops);ch=max(im.shape[0] for im in crops);cols=min(3,len(rows));pad=30
        frame=np.zeros((math.ceil(len(rows)/cols)*(ch+pad)+pad,cols*(cw+pad)+pad,3),np.uint8)
        for i,im in enumerate(crops):
            x=pad+(i%cols)*(cw+pad);y=pad+(i//cols)*(ch+pad);h,w=im.shape[:2];frame[y:y+h,x:x+w]=im
        return frame
    report=dict(scope='Offline Linux detector+hero+buttons+board benchmark. Synthetic tiled frames from reused labeled development crops, not Windows capture or independent live tables. Identical repeated tiles deliberately favor exact OCR reuse; diverse tiles are reported separately. No cross-frame caching. Cold means first call per scenario/mode in this process, not OS cold boot.',
                environment=dict(python=sys.version,platform=platform.platform(),cpu_model=cpu_model(),opencv=cv2.__version__,opencv_threads=cv2.getNumThreads(),OMP_THREAD_LIMIT=os.environ['OMP_THREAD_LIMIT']),sources=sources,scenarios=[])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    errors=[]
    scenarios=[(f'repeated_{n}',[repeated]*n) for n in (1,3,6)]+[(f'diverse_{n}',diverse[:n]) for n in (3,6)]
    for name,rows in scenarios:
        frame=scene(rows);metadata=dict(status='SUCCESS',image_shape=list(frame.shape),screen_origin=[0,0],hwnd=1,pid=1,process_created=0,executable='offline-benchmark')
        expected=sorted((tuple(row['hero']),tuple(row['board'])) for row in rows)
        entry=dict(name=name,table_count=len(rows),image_shape=list(frame.shape),expected=[dict(hero=list(h),board=list(b)) for h,b in expected],modes={});reference=None
        for enabled in (False,True):
            mode='memo' if enabled else 'baseline';samples=[]
            for sample in range(a.samples+1):
                started=time.perf_counter()
                with ocr_frame(enabled=enabled):result=analyze_tables(frame,metadata,read_buttons=True,read_community=True)
                elapsed=(time.perf_counter()-started)*1000
                signature=semantic(result)
                if reference is None:reference=signature
                same=signature==reference
                actual=sorted((tuple(row['hero_cards']),tuple(row.get('board',{}).get('cards',[]))) for row in result['tables'] if row['status']=='COMPLETE_CANDIDATE')
                matched=actual==expected
                if not same or not matched:errors.append(dict(scenario=name,mode=mode,sample=sample,semantic_same=same,expected_match=matched,actual=actual))
                measurement=dict(wall_ms=elapsed,timings_ms=result['timings_ms'],ocr_work=result.get('ocr_work'),semantic_same=same,expected_match=matched)
                if sample==0:entry['modes'][mode]=dict(first_call=measurement,semantic_reference=signature)
                else:samples.append(measurement)
                print(name,mode,sample,round(elapsed,1),'ms',result.get('ocr_work'),same,matched,flush=True)
            summary=dict(wall_ms=stats([s['wall_ms'] for s in samples]),stages_ms={k:stats([s['timings_ms'][k] for s in samples]) for k in samples[0]['timings_ms']},ocr={k:stats([s['ocr_work'][k] for s in samples]) for k in samples[0]['ocr_work']})
            entry['modes'][mode].update(samples=samples,summary=summary)
        report['environment']['tesseract_version']=result.get('ocr',{}).get('version')
        report['methodology_limits']=['Five-sample p95 is exploratory and close to the largest observation, not stable tail-latency evidence.', 'Fixed baseline then memo order can introduce order/warmup bias.', 'Synthetic tiling is not proof of live six-table capacity; repeated identical tiles favor cache reuse.']
        entry['median_speedup']=entry['modes']['baseline']['summary']['wall_ms']['median']/entry['modes']['memo']['summary']['wall_ms']['median']
        report['scenarios'].append(entry);report['errors']=errors;a.output.write_text(json.dumps(report,indent=2))
    report['all_semantics_and_labels_match']=not errors;a.output.write_text(json.dumps(report,indent=2));return bool(errors)
if __name__=='__main__':raise SystemExit(main())
