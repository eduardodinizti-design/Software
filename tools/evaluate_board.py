"""Development replay, not independent generalization evidence."""
import argparse,json,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.community_cards import read_board
from table_reading.pipeline import configure_ocr
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
configure_ocr()
rows=json.loads((Path(__file__).resolve().parents[1]/'docs/table-reading/development-labels.json').read_text())['tables'];results=[]
for index,row in enumerate(rows):
 data=(args.assets/row['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
 im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR);x,y,w,h=row['box']
 result=read_board(im[y:y+h,x:x+w]);expected=['Jc','5d','3c'] if index==7 else []
 assert result['cards']==expected,(index,result)
 results.append(dict(source=row['source'],box=row['box'],expected=expected,result=result))
args.output.write_text(json.dumps(dict(scope='Reused development captures; one flop, seven empty board regions. Not turn/river validation.',results=results),indent=2))
print('8 development regions matched: 1 real flop (3 cards) and 7 empty regions.')
