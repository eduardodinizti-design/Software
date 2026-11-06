"""Replay manually rechecked legacy white-face cards; report all failures."""
import argparse,json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from table_reading.inspect_cards import inspect
from table_reading.community_cards import read_board
from table_reading.pipeline import configure_ocr
p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True);a=p.parse_args()
configure_ocr();labels=json.loads((a.fixtures/'labels.json').read_text());results=[]
summary=dict(images=0,hero_correct=0,hero_wrong=0,hero_unknown=0,board_card_correct=0,board_card_wrong=0,board_card_unknown=0,empty_boards_correct=0)
for key,expected in labels['cases'].items():
 f=a.fixtures/(key+'.png')
 if not f.exists():continue
 im=cv2.imread(str(f));h,w=im.shape[:2]
 hero=inspect(im,(0,0,w,h));cards=[c.get('card_candidate') for c in hero['hero_rank_candidates']]
 board=read_board(im,hero_cards=cards)
 for got,want in zip(cards,expected['hero']):summary['hero_unknown' if got is None else 'hero_correct' if got==want else 'hero_wrong']+=1
 for i,want in enumerate(expected['board']):
  got=board['cards'][i] if i<len(board['cards']) else None
  summary['board_card_unknown' if got is None else 'board_card_correct' if got==want else 'board_card_wrong']+=1
 if not expected['board'] and not board['cards']:summary['empty_boards_correct']+=1
 summary['images']+=1
 results.append(dict(file=f.name,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),expected=expected,hero_cards=cards,hero=hero,board=board,card_style='WHITE_FACE',labels_visually_rechecked=True))
 print(key,cards,board['cards'],board['status'],flush=True)
Path('docs/table-reading/legacy-replay-results.json').write_text(json.dumps(dict(scope='Eight existing crops from the same legacy video, visually rechecked. White-face card style differs from current colored-face calibration.',summary=summary,results=results),indent=2))
print(summary)
