"""Source-disjoint template checks against preserved OCR, with explicit training split."""
import os
os.environ.setdefault('OMP_THREAD_LIMIT','1')
import argparse,json,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from table_reading.action_buttons import read_action_buttons
from table_reading.fastpath import template_mode
from table_reading.ocr_runtime import ocr_frame
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
training={r['source'] for r in json.loads((ROOT/'table_reading/button_template_assets/provenance.json').read_text())['templates']}
rows=json.loads((ROOT/'docs/table-reading/button-development-observations.json').read_text())
rows+=json.loads((ROOT/'docs/table-reading/colored-board-expansion.json').read_text())
seen=set();results=[]
def signature(result):
 return dict(status=result['status'],hero_turn_confirmed=result['hero_turn_confirmed'],actions_allowed=result['actions_allowed'],buttons=[{k:v for k,v in b.items() if k not in ('ocr_readings','evidence','template_iou','template_margin')} for b in result['buttons']])
for row in rows:
 key=(row['source'],tuple(row['box']))
 if key in seen:continue
 seen.add(key);path=a.assets/row['source'];im=cv2.imread(str(path));x,y,w,h=row['box'];crop=im[y:y+h,x:x+w];outputs={}
 for enabled in (False,True):
  with template_mode(enabled),ocr_frame() as work:result=read_action_buttons(crop)
  outputs[str(enabled)]=dict(result=result,ocr_work=dict(work))
 same=signature(outputs['False']['result'])==signature(outputs['True']['result'])
 results.append(dict(source=row['source'],sha256=hashlib.sha256(path.read_bytes()).hexdigest(),table_box=row['box'],split='training_source' if row['source'] in training else 'source_disjoint',same=same,outputs=outputs))
 print(row['source'],results[-1]['split'],same,[(b.get('label'),b.get('evidence')) for b in outputs['True']['result']['buttons']],flush=True)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(scope='Real reused source crops. Disjoint means source PNG excluded from all template construction; OCR comparison is regression evidence, not new human ground truth.',results=results),indent=2))
assert all(r['same'] for r in results),'Semantic regression'
