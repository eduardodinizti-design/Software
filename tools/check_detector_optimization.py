"""Exact output parity against a supplied detector package snapshot; no OCR."""
import argparse,importlib,json,sys,types
from pathlib import Path
import cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from table_reading.automatic_table_crops import detect_table_crops
parser=argparse.ArgumentParser();parser.add_argument('--baseline',required=True);parser.add_argument('--assets',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
package=types.ModuleType('detector_baseline');package.__path__=[args.baseline];sys.modules[package.__name__]=package
old=importlib.import_module('detector_baseline.automatic_table_crops').detect_table_crops
rows=[]
for p in sorted(Path(args.assets).glob('*.png')):
    image=cv2.cvtColor(cv2.imread(str(p)),cv2.COLOR_BGR2RGB)
    before=[r.to_dict() for r in old(image)];after=[r.to_dict() for r in detect_table_crops(image)]
    rows.append(dict(source=p.name,identical=before==after,before=before,after=after))
result=dict(sources=len(rows),identical=sum(r['identical'] for r in rows),samples=rows)
Path(args.output).write_text(json.dumps(result,indent=2));print({k:v for k,v in result.items() if k!='samples'})
if result['identical']!=result['sources']:sys.exit(1)
