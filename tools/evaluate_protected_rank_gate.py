"""Feasibility only: temporarily lift protected-rank switch without changing thresholds.
No runtime edit, OCR call, or training-source expansion is performed.
"""
import argparse,hashlib,json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from table_reading import rank_templates as rt
from table_reading.card_alignment import locate_card_pair
from table_reading.community_cards import read_board
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();root=Path(__file__).resolve().parents[1]
training=set(json.loads((rt.ASSET_DIR/'source_split.json').read_text())['training_sources']);records=[]
def image(row):
 path=args.assets/row['source'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'];x,y,w,h=row['box'];return cv2.imread(str(path))[y:y+h,x:x+w]
def inspect(crop,expected,row,case,position,kind):
 with patch.object(rt,'OCR_ONLY_RANKS',frozenset()):result=rt.read_template_rank(crop)
 rank=result.get('rank') if result else None
 records.append(dict(source=row['source'],sha256=row['sha256'],source_disjoint=row['sha256'] not in training,case=case,position=position,kind=kind,expected=expected[0],candidate=rank,outcome='fallback' if rank is None else 'correct' if rank==expected[0] else 'wrong',result=result))
for row in json.loads((root/'docs/table-reading/hero-batch-small-aspect.json').read_text())['results']:
 im=image(row)
 if row['scale']!=1:im=cv2.resize(im,None,fx=row['scale'],fy=row['scale'])
 im=cv2.resize(im,(720,1280));dy=locate_card_pair(im)['vertical_offset']
 for pos,(expected,left) in enumerate(zip(row['expected'],(402,447))):inspect(im[1010+dy:1070+dy,left:left+42],expected,row,f"hero-{row['index']}-{row['scale']}",pos,'hero')
boards=json.loads((root/'docs/table-reading/colored-board-expansion.json').read_text());eight=json.loads((root/'docs/table-reading/board-batch-eight.json').read_text());eight['expected']=['2s','8h','5h'];boards.append(eight)
for index,row in enumerate(boards):
 raw=image(row);h,w=raw.shape[:2]
 for width in (575,702,835):
  im=cv2.resize(raw,(width,round(h*width/w)));crops=[]
  result=read_board(im,_rank=lambda crop:crops.append(crop) or {'rank':None},_suit=lambda crop:{'suit':None})
  assert len(crops)==len(row['expected']),(index,width)
  for pos,(expected,crop) in enumerate(zip(row['expected'],crops)):inspect(crop,expected,row,f'board-{index}-{width}',pos,'board')
summary={}
for rank in ('A','4','3','8'):
 positive=[r for r in records if r['expected']==rank and r['source_disjoint']]
 negative=[r for r in records if r['candidate']==rank and r['expected']!=rank]
 summary[rank]=dict(source_disjoint_positive_sources=len({r['sha256'] for r in positive}),source_disjoint_positive_occurrences=len(positive),source_disjoint_correct_shortcuts=sum(r['candidate']==rank for r in positive),false_acceptances=len(negative),false_cases=[r['case'] for r in negative])
report=dict(scope='Temporary switch-only proposal, thresholds unchanged; all known Hero102 and six board sources×3widths; no OCR. Reused development samples, not independent hands.',decision='KEEP_ALL_PROTECTED_RANKS_ON_OCR',summary=summary,records=records)
args.output.write_text(json.dumps(report,indent=2));print(json.dumps(summary,indent=2))
