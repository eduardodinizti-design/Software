"""Evaluate automatic pixel proposals against pre-existing development labels."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from table_reading.pipeline import analyze_tables

def overlap(a,b):
 x,y,w,h=a;u,v,s,t=b
 inter=max(0,min(x+w,u+s)-max(x,u))*max(0,min(y+h,v+t)-max(y,v))
 return inter/(w*h+s*t-inter)

def main():
 p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 labels=json.loads((Path(__file__).resolve().parents[1]/'docs/table-reading/development-labels.json').read_text())['tables']
 summary=dict(tables=len(labels),detected=0,correct=0,wrong=0,unknown=0);results=[]
 for row in labels:
  data=(args.assets/row['source']).read_bytes()
  assert hashlib.sha256(data).hexdigest()==row['sha256'],'Fixture hash mismatch'
  frame=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
  meta=dict(status='SUCCESS',image_shape=list(frame.shape),screen_origin=[0,0],hwnd=1,pid=1,process_created=1,executable='PPPoker.exe',timestamp='DEVELOPMENT_FIXTURE')
  report=analyze_tables(frame,meta)
  candidates=[r for r in report['tables'] if r['status']=='COMPLETE_CANDIDATE' and overlap(r['local_box'],row['box'])>.90]
  cards=candidates[0]['hero_cards'] if len(candidates)==1 else [None,None]
  summary['detected']+=int(len(candidates)==1)
  for got,want in zip(cards,row['expected']):summary['unknown' if got is None else 'correct' if got==want else 'wrong']+=1
  result=dict(source=row['source'],expected=row['expected'],cards=cards,report=report)
  results.append(result);print(row['source'],cards,flush=True)
 args.output.parent.mkdir(parents=True,exist_ok=True)
 args.output.write_text(json.dumps(dict(summary=summary,scope='Previously used development screenshots; not independent generalization or latest user GDI frame.',results=results),indent=2))
 print(summary)
 if summary["wrong"] or summary["unknown"] or summary["detected"] != summary["tables"]:
  raise SystemExit(1)

if __name__=='__main__':main()
