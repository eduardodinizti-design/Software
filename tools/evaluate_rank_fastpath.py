"""Source-disjoint acceptance audit of real-glyph shortcut, without OCR."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from table_reading.rank_templates import read_template_rank,ASSET_DIR
from table_reading.card_alignment import locate_card_pair
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();root=Path(__file__).resolve().parents[1]
training={r['source_sha256'] for r in json.loads((ASSET_DIR/'manifest.json').read_text())['templates']}
baseline=json.loads((root/'docs/table-reading/hero-batch-small-aspect.json').read_text())['results'];out=[]
for row in baseline:
 data=(args.assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
 x,y,w,h=row['box'];table=cv2.imread(str(args.assets/row['source']))[y:y+h,x:x+w]
 if row['scale']!=1:table=cv2.resize(table,None,fx=row['scale'],fy=row['scale'])
 table=cv2.resize(table,(720,1280));dy=locate_card_pair(table)['vertical_offset']
 for position,(expected,left) in enumerate(zip(row['expected'],(402,447))):
  result=read_template_rank(table[1010+dy:1070+dy,left:left+42]);rank=result['rank'] if result else None
  out.append(dict(index=row['index'],scale=row['scale'],source=row['source'],sha256=row['sha256'],source_disjoint=row['sha256'] not in training,position=position,expected=expected[0],rank=rank,outcome='fallback' if rank is None else 'correct' if rank==expected[0] else 'wrong',result=result))
summary={}
for group in ('all','source_disjoint','training_source'):
 subset=[r for r in out if group=='all' or (r['source_disjoint'] if group=='source_disjoint' else not r['source_disjoint'])]
 summary[group]={k:sum(r['outcome']==k for r in subset) for k in ('correct','wrong','fallback')}
args.output.write_text(json.dumps(dict(scope='Shortcut acceptance only. Reused development sources; transformations are not independent hands. Training-source matches are not validation.',summary=summary,results=out),indent=2));print(summary)

if summary["all"]["wrong"]:
 raise SystemExit("Incorrect accepted template rank; inspect report")
