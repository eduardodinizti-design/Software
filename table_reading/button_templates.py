"""Whole-label ink templates for validated static button labels only."""
from functools import lru_cache
from pathlib import Path
import hashlib,json
import cv2
import numpy as np

ASSETS=Path(__file__).with_name('button_template_assets')
# Call-with-amount is deliberately unsupported; no prefix matching is performed.
LABELS=('F/C','Check','Fold','Raise')
# Enabled only after source-disjoint whole-label validation.
ENABLED_LABELS=frozenset(('F/C','Check','Fold','Raise'))

def normalize(clean):
    if not isinstance(clean,np.ndarray) or clean.dtype!=np.uint8 or clean.ndim!=2 or not clean.size or clean.size>2_000_000:
        return None
    ink=np.uint8(clean<128)*255
    points=cv2.findNonZero(ink)
    if points is None:return None
    x,y,w,h=cv2.boundingRect(points)
    if h<8 or w<6:return None
    ratio=w/h
    if not .25<=ratio<=12:return None
    # Preserve all ink, including digits, currency and unrecognized suffixes.
    mask=cv2.resize(ink[y:y+h,x:x+w],(max(1,round(32*ratio)),32),interpolation=cv2.INTER_AREA)>127
    return mask,ratio

@lru_cache(maxsize=1)
def templates():
    result=[]
    try:
        rows=json.loads((ASSETS/'provenance.json').read_text())['templates']
        if {row['label'] for row in rows}!=set(LABELS):return ()
        for row in rows:
            filename=row['file']
            if Path(filename).name!=filename:return ()
            path=ASSETS/filename
            if hashlib.sha256(path.read_bytes()).hexdigest()!=row['template_sha256']:return ()
            clean=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
            normalized=normalize(clean)
            if normalized is None:return ()
            result.append((row['label'],*normalized))
    except (OSError,ValueError,KeyError,TypeError):return ()
    return result

def read_static_label(clean):
    normalized=normalize(clean)
    if normalized is None:return None
    mask,ratio=normalized;by_label={}
    for label,template,aspect in templates():
        if abs(ratio/aspect-1)>.035:
            by_label.setdefault(label,0.);continue
        resized=cv2.resize(np.uint8(mask),(template.shape[1],32),interpolation=cv2.INTER_NEAREST)>0
        union=np.count_nonzero(resized|template)
        score=np.count_nonzero(resized&template)/union if union else 0.
        by_label[label]=max(score,by_label.get(label,0.))
    scores=sorted(((score,label) for label,score in by_label.items()),reverse=True)
    if not scores or scores[0][0]<.90 or scores[0][1] not in ENABLED_LABELS:return None
    margin=scores[0][0]-(scores[1][0] if len(scores)>1 else 0.)
    if margin<.12:return None
    return dict(label=scores[0][1],evidence='WHOLE_LABEL_TEMPLATE',template_iou=round(scores[0][0],4),template_margin=round(margin,4))
