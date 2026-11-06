"""Reproduce five visually labeled colored boards; reused development sources."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.community_cards import read_board
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);args=p.parse_args()
rows=json.loads((Path(__file__).resolve().parents[1]/'docs/table-reading/colored-board-expansion.json').read_text())
for row in rows:
 data=(args.assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
 image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);x,y,w,h=row['box']
 result=read_board(image[y:y+h,x:x+w])
 assert result['cards']==row['expected'],(row['source'],result)
 print(row['source'],result['street'],result['cards'],flush=True)
print('5 colored-board regions, 17 card occurrences matched; 4 flops and 1 river, no real turn.')
