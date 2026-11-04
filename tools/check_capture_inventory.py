"""Inventory detector outputs on existing screenshots; counts are not approvals."""
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
from visualpilot.pppoker.table_boundaries import detect_control_anchored_tables


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rows=[]
    for path in sorted((ROOT/'public/assets/aistudio').glob('*.png')):
        frame=np.array(Image.open(path).convert('RGB'))
        anchors=detect_control_anchored_tables(frame)
        boxes=MultiTableTracker().detect_tables_from_unity_pixels(frame)
        rows.append({'fixture':str(path.relative_to(ROOT)),
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                     'size':[frame.shape[1],frame.shape[0]],
                     'anchored_candidates':anchors,'all_candidates':boxes,
                     'ocr_approved':False})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'scope':'Offline inventory, no ground-truth accuracy claim','results':rows},indent=2)+'\n')
    print(f'{len(rows)} screenshots; {sum(bool(r["all_candidates"]) for r in rows)} with candidates')
    for row in rows:
        if row['all_candidates']:
            print(Path(row['fixture']).name, row['anchored_candidates'], row['all_candidates'])

if __name__=='__main__':
    main()
