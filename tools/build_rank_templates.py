"""Rebuild small rank glyphs from explicitly labeled real development sources."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from table_reading.rank_templates import segmented_masks,ASSET_DIR
from table_reading.card_alignment import locate_card_pair
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'docs/table-reading/eight-search.json').read_text())['entries']
# Explicitly labeled in the Hero batch, choosing a single clear source per rank.
choices={1:['Q','4'],2:['A','K'],5:['T','5'],7:['3','Q'],9:['J','2'],10:['9','2'],14:['7','6']}
ASSET_DIR.mkdir(exist_ok=True);manifest=[];used=set()
def save(rank,crop,provenance,variant=None):
 if rank in used and variant is None:return
 masks=segmented_masks(crop)
 if len(masks)!=2:raise ValueError(f'Cannot segment training rank {rank}')
 used.add(rank)
 for index,(glyph,_) in enumerate(masks):
  name=f'{rank}-{index}.png' if variant is None else f'{rank}-{variant}-{index}.png';cv2.imwrite(str(ASSET_DIR/name),glyph)
  manifest.append(dict(rank=rank,asset=name,asset_sha256=hashlib.sha256((ASSET_DIR/name).read_bytes()).hexdigest(),threshold_fraction=(.6,.8)[index],**provenance))
for index,labels in choices.items():
 row=rows[index];path=args.assets/row['source'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
 x,y,w,h=row['box'];im=cv2.imread(str(path))[y:y+h,x:x+w];table=cv2.resize(im,(720,1280));dy=locate_card_pair(table)['vertical_offset']
 for rank,left in zip(labels,(402,447)):
  save(rank,table[1010+dy:1070+dy,left:left+42],dict(source=row['source'],source_sha256=row['sha256'],table_box=row['box'],roi_canonical=[left,1010+dy,42,60],label_basis='Hero batch visual transcription',role='competitor_only' if rank in 'A438' else 'candidate'))
# Add genuine resampling variants from the exact same training screenshots.
# No source-disjoint screenshot is used, and thresholds are unchanged.
for index,labels in choices.items():
 row=rows[index];x,y,w,h=row['box'];im=cv2.imread(str(args.assets/row['source']))[y:y+h,x:x+w]
 for scale in (.5,.75,1.25):
  reduced=cv2.resize(im,None,fx=scale,fy=scale)
  table=cv2.resize(reduced,(720,1280));dy=locate_card_pair(table)['vertical_offset']
  for slot,(rank,left) in enumerate(zip(labels,(402,447))):
   save(rank,table[1010+dy:1070+dy,left:left+42],dict(source=row['source'],source_sha256=row['sha256'],table_box=row['box'],roi_canonical=[left,1010+dy,42,60],scale=scale,label_basis='Transformed existing labeled training screenshot; not independent evidence',role='competitor_only' if rank in 'A438' else 'candidate'),variant=f'i{index}s{str(scale).replace(".","p")}p{slot}')
# The colored 8 is a competitor only; this screenshot cannot be holdout evidence.
eight=json.loads((root/'docs/table-reading/board-batch-eight.json').read_text());path=args.assets/eight['source'];assert hashlib.sha256(path.read_bytes()).hexdigest()==eight['sha256']
x,y,w,h=eight['box'];table=cv2.imread(str(path))[y:y+h,x:x+w]
from table_reading.community_cards import read_board
r=read_board(table,_rank=lambda crop:dict(rank=None),_suit=lambda crop:dict(suit=None))
x,y,w,h=r['candidates'][1];face=cv2.resize(table[y:y+h,x:x+w],(90,130))
save('8',face[3:53,4:44],dict(source=eight['source'],source_sha256=eight['sha256'],table_box=eight['box'],board_card_box=[x,y,w,h],face_roi=[4,3,40,50],label_basis='Manually labeled real board 2s/8h/5h',role='competitor_only'))
split=json.loads((ASSET_DIR/'source_split.json').read_text())
assert {r['source_sha256'] for r in manifest}==set(split['training_sources']), 'Training-source split changed'
assert not ({r['source_sha256'] for r in manifest}&set(split['evaluation_sources'])), 'Evaluation-source leakage'
(ASSET_DIR/'manifest.json').write_text(json.dumps(dict(scope='Real development glyphs plus resized variants from the same fixed training sources; source-disjoint images excluded. Transforms are not independent evidence.',templates=manifest),indent=2))
print('ranks',sorted(used),'glyphs',len(manifest))
