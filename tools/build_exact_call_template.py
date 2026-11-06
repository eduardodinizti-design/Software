"""Rebuild the exact whole Call1.0 mask from its single real training source."""
import argparse,hashlib,json
from pathlib import Path
import cv2
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);a=p.parse_args()
out=Path('table_reading/button_template_assets');r=json.loads((out/'exact_call_provenance.json').read_text());source=a.assets/r['training_source'];data=source.read_bytes();assert hashlib.sha256(data).hexdigest()==r['training_source_sha256']
im=cv2.imread(str(source));tx,ty,_,_=r['table_box'];x,y,w,h=r['button_box'];region=im[ty+y+round(h*.18):ty+y+round(h*.82),tx+x+round(w*.08):tx+x+round(w*.92)];hsv=cv2.cvtColor(region,cv2.COLOR_BGR2HSV);ink=((hsv[:,:,1]<85)&(hsv[:,:,2]>165)).astype('uint8')*255
xx,yy,ww,hh=cv2.boundingRect(cv2.findNonZero(ink));native=ink[yy:yy+hh,xx:xx+ww];assert list(native.shape)==r['native_ink_shape']
clean=cv2.resize(255-native,None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST);assert list(clean.shape)==r['clean_ink_shape'];path=out/r['asset'];cv2.imwrite(str(path),clean);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['asset_sha256']
print('Exact training raster rebuilt and hash verified')
