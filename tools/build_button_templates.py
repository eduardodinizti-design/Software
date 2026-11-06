"""Rebuild visually checked prototype masks from documented real sources."""
import cv2,json,hashlib
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);a=p.parse_args()
assets=a.assets;out=Path('table_reading/button_template_assets');out.mkdir(parents=True,exist_ok=True)
rows=json.load(open('docs/table-reading/button-development-observations.json'))
provenance=[]
for label,ri,bi in [('F/C',0,0),('Check',1,1),('Fold',6,0),('Raise',6,2)]:
 row=rows[ri];data=(assets/row['source']).read_bytes();im=cv2.imread(str(assets/row['source']));tx,ty,_,_=row['box'];x,y,w,h=row['result']['buttons'][bi]['box']
 region=im[ty+y+round(h*.18):ty+y+round(h*.82),tx+x+round(w*.08):tx+x+round(w*.92)]
 hsv=cv2.cvtColor(region,cv2.COLOR_BGR2HSV);ink=((hsv[:,:,1]<85)&(hsv[:,:,2]>165)).astype('uint8')*255
 clean=cv2.resize(255-ink,None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST);clean=cv2.copyMakeBorder(clean,12,12,12,12,cv2.BORDER_CONSTANT,value=255)
 path=out/(label.replace('/','_')+'.png');cv2.imwrite(str(path),clean)
 provenance.append(dict(label=label,source=row['source'],source_sha256=hashlib.sha256(data).hexdigest(),table_box=row['box'],button_box=row['result']['buttons'][bi]['box'],template_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),basis='Source text visually checked; whole text mask, no font rendering'))
(out/'provenance.json').write_text(json.dumps(dict(scope='Four prototypes from three development sources. Only F/C and Check enabled after source-disjoint verification; Fold/Raise diagnostic competitors only. Bare Call and Bet unsupported; OCR fallback.',templates=provenance),indent=2))
