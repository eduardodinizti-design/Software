"""Rebuild whole-label masks from visually checked provenance rectangles."""
import argparse,hashlib,json
from pathlib import Path
import cv2
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);a=p.parse_args()
out=Path('table_reading/button_template_assets');manifest=out/'provenance.json';provenance=json.loads(manifest.read_text())
for row in provenance['templates']:
 path=a.assets/row['source'];data=path.read_bytes()
 assert hashlib.sha256(data).hexdigest()==row['source_sha256'],row['source']
 im=cv2.imread(str(path));tx,ty,_,_=row['table_box'];x,y,w,h=row['button_box']
 region=im[ty+y+round(h*.18):ty+y+round(h*.82),tx+x+round(w*.08):tx+x+round(w*.92)]
 hsv=cv2.cvtColor(region,cv2.COLOR_BGR2HSV);ink=((hsv[:,:,1]<85)&(hsv[:,:,2]>165)).astype('uint8')*255
 clean=cv2.resize(255-ink,None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST);clean=cv2.copyMakeBorder(clean,12,12,12,12,cv2.BORDER_CONSTANT,value=255)
 output=out/row['file'];cv2.imwrite(str(output),clean)
 assert hashlib.sha256(output.read_bytes()).hexdigest()==row['template_sha256'],row['file']
print('Rebuilt and verified',len(provenance['templates']),'real-source masks')
