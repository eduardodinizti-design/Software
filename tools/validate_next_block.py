"""End-to-end offline detector + hero + board replay, with explicit derived negatives."""
import os
os.environ.setdefault('OMP_THREAD_LIMIT', '1')
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from table_reading.pipeline import analyze_tables


def run(assets, output):
    root = Path(__file__).resolve().parents[1]
    labels = json.loads((root/'docs/table-reading/development-labels.json').read_text())['tables']
    flop = labels[7]
    special = '_8C143E80-F85C-4DE6-ADCD-0641771AE2E6__2a4e7ea0.png'
    sources = {}
    def load(source, digest=None):
        data = (assets/source).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if digest and digest != actual:
            raise ValueError(f'Source hash mismatch: {source}')
        sources[source] = actual
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    eight = load(special)
    image = load(flop['source'], flop['sha256'])
    x,y,w,h = flop['box']
    expected = ['Jc','5d','3c']
    spectator = image.copy()
    # Erase only hero faces in the labeled table; preserve all detector inputs
    # elsewhere. This is an artificial absent-hero case, not a real spectator.
    spectator[y+round(h*.79):y+round(h*.89), x+round(w*.55):x+round(w*.74)] = (160,65,30)
    empty = image.copy()
    empty[y+round(h*.35):y+round(h*.50), x+round(w*.17):x+round(w*.85)] = (160,65,30)
    partial = image.copy()
    partial[y+383:y+478, x+189:x+254] = (160,65,30)
    cases = [
        ('eight_full_source',eight,special,['2s','8h','5h'],'unaltered full source; no manual crop'),
        ('flop_full_source',image,flop['source'],expected,'unaltered full source'),
        ('spectator_derived',spectator,flop['source'],expected,'hero face area replaced by felt'),
        ('empty_board_derived',empty,flop['source'],None,'board area replaced by felt'),
        ('partial_board_derived',partial,flop['source'],None,'middle community card replaced by felt'),
        ('recovered_full_source',image,flop['source'],expected,'unaltered full source after invalid observations'),
        ('blank_frame',np.zeros_like(image),None,None,'all pixels black'),
    ]
    results=[]
    for name,frame,source,expected,transformation in cases:
        metadata=dict(status='SUCCESS',image_shape=list(frame.shape),screen_origin=[0,0],
                      hwnd=1,pid=1,process_created=0,executable='offline-fixture',timestamp=None)
        result=analyze_tables(frame,metadata,read_community=True)
        accepted=[r['board']['cards'] for r in result['tables']
                  if r.get('board',{}).get('status')=='EXPERIMENTAL_BOARD']
        exact = accepted == [expected] if expected is not None else not accepted
        errors=[]
        if not exact: errors.append('BOARD_EXPECTATION_MISMATCH')
        if result['actions_allowed'] or any(r['actions_allowed'] for r in result['tables']):
            errors.append('ACTIONS_ENABLED')
        if name=='spectator_derived' and any(any(r['hero_cards']) for r in result['tables']
                if r.get('board',{}).get('cards')==expected):
            errors.append('ERASED_HERO_ACCEPTED')
        results.append(dict(case=name,source=source,transformation=transformation,
                            expected_board=expected,accepted_boards=accepted,passed=not errors,
                            errors=errors,result=result))
        print(name,'PASS' if not errors else 'FAIL',accepted,flush=True)
    report=dict(scope='Seven offline pipeline calls using two reused development sources. Synthetic metadata does not validate Windows capture. Spectator, empty, partial and blank cases are explicit transformations. Detection is never injected or bypassed.',
                detector_sha256=hashlib.sha256(Path(analyze_tables.__globals__['detect_table_crops'].__code__.co_filename).read_bytes()).hexdigest(),
                sources=sources,summary=dict(total=len(results),passed=sum(r['passed'] for r in results),failed=sum(not r['passed'] for r in results)),results=results)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2))
    return report['summary']['failed']


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(bool(run(args.assets,args.output)))
