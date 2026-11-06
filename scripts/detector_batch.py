"""Reproducible detector evidence; transformed captures are not live validation."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from table_reading import table_corner_anchors as anchors
from table_reading.automatic_table_crops import detect_table_crops

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--assets',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();root=Path(args.assets)
    rows=json.loads(Path('docs/table-reading/development-labels.json').read_text())['tables']
    extract=anchors._menu_stripes
    def measure(image, enabled):
        anchors._menu_stripes=extract if enabled else lambda mask:mask
        try:return anchors.corner_evidence(image)
        finally:anchors._menu_stripes=extract
    transformed=[]
    for row in rows:
        im=cv2.imread(str(root/row['source']));x,y,w,h=row['box']
        if im is None:raise FileNotFoundError(row['source'])
        crop=cv2.cvtColor(im[y:y+h,x:x+w],cv2.COLOR_BGR2RGB);crop[round(h*.93):]=0
        for scale in (1,.75,.5):
            image=cv2.resize(crop,None,fx=scale,fy=scale)
            transformed.append(dict(source=row['source'],box=row['box'],scale=scale,before=measure(image,False),after=measure(image,True)))
    raw=[]
    for path in sorted(root.glob('*.png')):
        im=cv2.imread(str(path));rgb=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)
        anchors._menu_stripes=lambda mask:mask
        try:before=[r.to_dict() for r in detect_table_crops(rgb)]
        finally:anchors._menu_stripes=extract
        after=[r.to_dict() for r in detect_table_crops(rgb)]
        raw.append(dict(source=path.name,before=before,after=after))
    result=dict(scope='Raw corpus inventory is not precision/recall. Button removal and scaling are synthetic transformations of real captures.',
      transformed=dict(n=len(transformed),before_accepted=sum(r['before']['accepted'] for r in transformed),after_accepted=sum(r['after']['accepted'] for r in transformed),samples=transformed),raw=raw)
    Path(args.output).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result['transformed'].items() if k!='samples'}));print('raw_sources',len(raw))
if __name__=='__main__':main()
