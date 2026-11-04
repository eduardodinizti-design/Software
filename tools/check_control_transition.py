"""Replay a derived control-visibility sequence; no desktop access or clicks.

The hidden-controls frame is synthetic editing of an existing screenshot, NOT
an actual consecutive PPPoker capture. Exit 1 reports missing continuity.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'repo_visualpilot'))
import numpy as np
from PIL import Image
from visualpilot.pppoker.multi_table_tracker import MultiTableTracker

FIXTURE='public/assets/aistudio/_21D744E1-8BE6-4C79-82AF-5582DD6A9547__6988a9e2.png'


def run_sequence():
    path=ROOT/FIXTURE
    visible=np.array(Image.open(path).convert('RGB'))
    hidden=visible.copy()
    hidden[1194:1260,25:700]=[15,25,40]
    tracker=MultiTableTracker()
    frames=[('visible',visible),('hidden_1',hidden),('hidden_2',hidden),('visible_again',visible)]
    steps=[]
    for name, frame in frames:
        tables=tracker.scan_unity_surface(frame)
        steps.append({'step':name,'tables':[{'id':t.table_id,'box':t.box_physical,
            'status':t.status,'geometry_version':t.geometry_version} for t in tables],
            'active_count':len(tracker.active_tables)})
    initial_id=steps[0]['tables'][0]['id'] if len(steps[0]['tables'])==1 else None
    passed=initial_id is not None and all(len(s['tables'])==1 and s['tables'][0]['id']==initial_id for s in steps)
    return {'passed':passed,'scope':'Derived screenshot replay; not native Windows or live transition',
        'fixture':FIXTURE,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'transformation':{'box':[25,1194,675,66],'fill_rgb':[15,25,40]},'steps':steps}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=run_sequence()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS' if report['passed'] else 'FAIL: continuous table detection not established')
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
