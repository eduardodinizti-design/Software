"""Offline crop acceptance check. Never connects to a client or dispatches input.

Reference boxes are manual annotations for this exact fixture, not runtime ROIs.
Exit 1 means the detector is not ready for complete-table OCR.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'repo_visualpilot'))
import numpy as np
from PIL import Image
from visualpilot.pppoker.multi_table_tracker import MultiTableTracker

FIXTURE = 'public/assets/aistudio/_21D744E1-8BE6-4C79-82AF-5582DD6A9547__6988a9e2.png'
# Manually inspected left PPPoker table. Other clients/occluded tables are excluded.
REGIONS = {
    'visible_table': (12, 36, 698, 1242),
    'hero_cards': (405, 1025, 110, 108),
    'hero_stack': (297, 1144, 127, 33),
    'upper_player_stack': (297, 269, 128, 31),
    'action_controls': (25, 1194, 675, 66),
}


def coverage(candidate, region):
    x,y,w,h = candidate
    a,b,c,d = region
    return max(0, min(x+w,a+c)-max(x,a))*max(0,min(y+h,b+d)-max(y,b))/(c*d)


def assess(candidates, regions=REGIONS):
    evaluations = []
    for box in candidates:
        measures = {name: coverage(box, region) for name,region in regions.items()}
        # Avoid approving a whole-desktop bounding box that contains every ROI.
        reference_area = regions['visible_table'][2]*regions['visible_table'][3]
        tightness = coverage(box, regions['visible_table'])*reference_area/(box[2]*box[3])
        passed = all(value >= .98 for value in measures.values()) and tightness >= .90
        evaluations.append({'box':list(box), 'coverage':measures, 'tightness':tightness, 'passed':passed})
    return {'passed':any(item['passed'] for item in evaluations), 'candidates':evaluations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    path = ROOT / FIXTURE
    frame = np.asarray(Image.open(path).convert('RGB'))
    report = assess(MultiTableTracker().detect_tables_from_unity_pixels(frame))
    report.update(fixture=FIXTURE, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  image_size=[frame.shape[1],frame.shape[0]], reference_regions=REGIONS,
                  scope='Offline screenshot geometry only; not OCR accuracy or Windows validation')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS' if report['passed'] else 'FAIL: complete table not detected')
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
