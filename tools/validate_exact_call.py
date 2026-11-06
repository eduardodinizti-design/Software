"""Exact Call1.0 native-raster validation and paired whole-button-row measurements."""
import os
os.environ['OMP_THREAD_LIMIT']='1'
import argparse,json,hashlib,statistics,sys,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.action_buttons import read_action_buttons
from table_reading.button_templates import read_exact_call
from table_reading.ocr_runtime import ocr_frame
from table_reading.fastpath import template_mode
cv2.setNumThreads(1)
ROOT=Path(__file__).resolve().parents[1]

def semantic(result):
    if isinstance(result,dict):return {k:semantic(v) for k,v in result.items() if k not in ('ocr_readings','evidence','template_iou','template_margin')}
    if isinstance(result,list):return [semantic(v) for v in result]
    return result

def stats(v):return dict(n=len(v),median=float(statistics.median(v)),p95=float(np.percentile(v,95)))

def main():
    p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--samples',type=int,default=5);a=p.parse_args()
    if a.samples<5:p.error('At least5warm samples')
    rows=json.loads((ROOT/'docs/table-reading/button-expanded-validation.json').read_text())['results'];cases=[];negatives=[]
    for row in rows:
        calls=[b for b in row['outputs']['False']['result']['buttons'] if (b.get('label') or '').startswith('Call ')]
        if not calls:continue
        path=a.assets/row['source'];data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
        im=cv2.imread(str(path));x,y,w,h=row['table_box'];crop=im[y:y+h,x:x+w];cleans=[]
        def capture(clean,mode):
            if mode==7:cleans.append(clean.copy())
            return ''
        read_action_buttons(crop,_ocr=capture)
        for index,button in enumerate(row['outputs']['False']['result']['buttons']):
            if not (button.get('label') or '').startswith('Call '):continue
            result=read_exact_call(cleans[index]);expected_exact=row['source'].startswith(('_4528','_58CB','_76D7'))
            assert bool(result)==expected_exact,(row['source'],button['label'],result)
            negatives.append(dict(source=row['source'],sha256=row['sha256'],label=button['label'],expected_exact=expected_exact,exact_result=result))
            if expected_exact:cases.append((row,crop))
    report=dict(scope='Whole-label exact-mask shortcut only; three same-label real source screenshots, one training and two source-disjoint. Paired row timings exclude capture/detection. Five warm samples per mode plus first calls; p95 exploratory.',OMP_THREAD_LIMIT='1',opencv_threads=cv2.getNumThreads(),raster_checks=negatives,scenarios=[])
    for row,crop in cases:
        samples={False:[],True:[]};cold={};reference=None
        for i in range(a.samples+1):
            for enabled in ((False,True) if i%2==0 else (True,False)):
                started=time.perf_counter()
                with template_mode(True),ocr_frame() as work:
                    if enabled:result=read_action_buttons(crop)
                    else:
                        with patch('table_reading.action_buttons.read_exact_call',return_value=None):result=read_action_buttons(crop)
                elapsed=(time.perf_counter()-started)*1000;s=semantic(result)
                if reference is None:reference=s
                assert s==reference,(row['source'],enabled,i)
                assert result['status']=='PRESELECTION_ROW' and all(b['action'] is None for b in result['buttons'])
                call=result['buttons'][1];assert call['amount']=='1.0' and call['unit']=='BB'
                observation=dict(ms=elapsed,ocr_work=dict(work),result=result)
                if i==0:cold[str(enabled)]=observation
                else:samples[enabled].append(observation)
        modes={str(enabled):dict(samples=values,ms=stats([v['ms'] for v in values]),ocr_calls=stats([v['ocr_work']['calls'] for v in values])) for enabled,values in samples.items()}
        report['scenarios'].append(dict(source=row['source'],source_split='training' if row['source'].startswith('_4528') else 'source_disjoint',cold=cold,modes=modes,semantic_reference=reference))
        print(row['source'],{k:(v['ms'],v['ocr_calls']) for k,v in modes.items()},flush=True)
    report['all_checks_passed']=True;a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
