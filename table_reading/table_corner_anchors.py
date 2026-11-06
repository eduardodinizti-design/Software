"""Calibrated blue-layout corner cues independent of action controls."""
from pathlib import Path
import cv2
import numpy as np

REGIONS={'menu':(0,0,65,70),'signal':(335,0,65,70),'cards':(0,590,60,60),'chat':(340,590,60,60)}

def shape(mask):
    ys,xs=np.where(mask>0)
    if not len(xs):return None
    mask=mask[ys.min():ys.max()+1,xs.min():xs.max()+1]
    h,w=mask.shape;scale=36/max(w,h)
    small=cv2.resize(mask,(max(1,round(w*scale)),max(1,round(h*scale))),interpolation=cv2.INTER_AREA)>127
    out=np.zeros((44,44),bool);yy=(44-small.shape[0])//2;xx=(44-small.shape[1])//2
    out[yy:yy+small.shape[0],xx:xx+small.shape[1]]=small
    return out

def _measure(rgb, native=False):
    a=rgb if native else cv2.resize(rgb,(400,704))
    hsv=cv2.cvtColor(a,cv2.COLOR_RGB2HSV)
    scores={}
    for name,(x,y,w,h) in REGIONS.items():
        if native:
            x,y,w,h=round(x*rgb.shape[1]/400),round(y*rgb.shape[0]/704),round(w*rgb.shape[1]/400),round(h*rgb.shape[0]/704)
        mask=cv2.inRange(hsv[y:y+h,x:x+w],(38,90,65),(90,255,255))
        if name=='chat' and np.any(mask):
            _,labels,stats,_=cv2.connectedComponentsWithStats(mask)
            mask=np.uint8(labels==(1+np.argmax(stats[1:,cv2.CC_STAT_AREA])))*255
        candidate=shape(mask)
        path=Path(__file__).with_name('table_anchor_templates')/(name+'.png')
        try:template=cv2.imdecode(np.frombuffer(path.read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
        except OSError:return {'accepted':False,'reason':'ANCHOR_TEMPLATE_MISSING','scores':{}}
        if template is None:return {'accepted':False,'reason':'ANCHOR_TEMPLATE_INVALID','scores':{}}
        reference=shape(template)
        score=0.0
        if candidate is not None and reference is not None:
            score=float(np.logical_and(candidate,reference).sum()/max(1,np.logical_or(candidate,reference).sum()))
        scores[name]=round(score,4)
    return {'accepted':all(score>=.65 for score in scores.values()),'scores':scores,'reason':'FOUR_CORNER_ANCHORS'}


def corner_evidence(rgb):
    """Keep existing evidence first; retry masks before resizing, not looser scores.

    Every corner must pass in one complete measurement. Do not combine best
    corners across methods, infer missing icons, or lower the .65 threshold.
    """
    canonical=_measure(rgb)
    if canonical['accepted']:
        return dict(canonical,method='CANONICAL_RGB')
    native=_measure(rgb,native=True)
    if native['accepted']:
        return dict(native,method='NATIVE_MASK',canonical_scores=canonical['scores'])
    return dict(canonical,method='CANONICAL_RGB',native_scores=native['scores'])
