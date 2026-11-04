"""Isolated identity validation on resampled screenshot crops, not Windows capture.

Explicit boxes isolate association from detection. Pixel edits are simulated
content changes, not a recording of live animation. Exit 1 if stable identity is
lost in any unchanged/lower-only case or reused in an upper-change case.
"""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'repo_visualpilot'))
import cv2
import numpy as np
from PIL import Image
from visualpilot.pppoker.multi_table_tracker import MultiTableTracker


def run_matrix():
    path=ROOT/'public/assets/aistudio/_21D744E1-8BE6-4C79-82AF-5582DD6A9547__6988a9e2.png'
    crop=np.array(Image.open(path).convert('RGB'))[36:1273,11:714].copy()
    h,w=crop.shape[:2]
    def place(image):
        ih,iw=image.shape[:2]
        canvas=np.zeros((ih+80,iw+80,3),dtype=np.uint8)
        canvas[40:40+ih,40:40+iw]=image
        return canvas,[40,40,iw,ih]
    before,box=place(crop)
    cases=[]
    for name,method in [('nearest',cv2.INTER_NEAREST),('linear',cv2.INTER_LINEAR),('cubic',cv2.INTER_CUBIC),('area',cv2.INTER_AREA)]:
        for scale in (.75,1.25,2):
            for change in ('none','lower','upper'):
                edited=crop.copy()
                if change=='lower':
                    edited[int(h*.8):int(h*.88),int(w*.4):int(w*.6)]=[240,230,220]
                elif change=='upper':
                    edited[int(h*.04):int(h*.12),int(w*.3):int(w*.65)]=[255,255,0]
                resized=cv2.resize(edited,(round(w*scale),round(h*scale)),interpolation=method)
                after,new_box=place(resized)
                tracker=MultiTableTracker()
                first=tracker.scan_unity_surface(before,[box])[0]
                second=tracker.scan_unity_surface(after,[new_box])[0]
                same=first.table_id==second.table_id
                passed=(not same and second.status=='AMBIGUOUS') if change=='upper' else (same and second.status=='CANDIDATE')
                cases.append({'interpolation':name,'scale':scale,'change':change,'same_id':same,'status':second.status,'passed':passed})
    continuity=[c for c in cases if c['change']!='upper']
    rejection=[c for c in cases if c['change']=='upper']
    return {'scope':'Explicit boxes; real screenshot pixels; simulated edits/resampling; no Windows or detection validation',
            'cases':cases,'continuity_passed':sum(c['passed'] for c in continuity),'continuity_total':len(continuity),
            'upper_change_rejected':sum(c['passed'] for c in rejection),'upper_change_total':len(rejection),
            'passed':all(c['passed'] for c in cases)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=run_matrix()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print({k:v for k,v in report.items() if k!='cases'})
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
