"""Four-colour deck recognition from observed card faces, including a shape-tested spade."""
from pathlib import Path
import re
import cv2
import numpy as np

def largest(mask):
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'))
    if count<=1:return mask.astype('uint8')*255
    chosen=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    return (labels==chosen).astype('uint8')*255

def normalized(mask):
    mask=largest(mask>100);x,y,w,h=cv2.boundingRect(mask)
    if not w or not h:return np.zeros((28,24),dtype=bool)
    return cv2.resize(mask[y:y+h,x:x+w],(24,28))>100


def face(reader,rgb,box,minimum_confidence=.9):
    x,y,w,h=box
    surface=rgb[y+2:y+h-2,x+2:x+w-2].astype('int16')
    paper=((surface.min(axis=2)>100)&((surface.max(axis=2)-surface.min(axis=2))<35)).mean() if surface.size else 0
    if paper<.45:return None,'',0.,None
    rank,score=reader.field(rgb[y:y+int(h*.32),x:x+int(w*.57)])
    if not re.fullmatch(r'(?:[2-9TJQKA]|10)',rank.upper()) or score<minimum_confidence:
        rank,score=reader.field(rgb[y:y+int(h*.43),x:x+int(w*.55)])
    if not re.fullmatch(r'(?:[2-9TJQKA]|10)',rank.upper()) or score<minimum_confidence:
        crop=rgb[y:y+int(h*.38),x:x+int(w*.57)]
        value,confidence=reader.field(crop)
        if confidence>score:rank,score=value,confidence
        if not re.fullmatch(r'(?:[2-9TJQKA]|10)',rank.upper()) or score<minimum_confidence:
            _,binary=cv2.threshold(cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY),0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
            value,confidence=reader.field(np.repeat(binary[:,:,None],3,axis=2))
            if confidence>score:rank,score=value,confidence
    rank=rank.upper();rank='T' if rank=='10' else rank
    pixels=rgb[y+int(h*.47):y+h-3,x+int(w*.3):x+w-3].astype('int16')
    if pixels.size==0:return None,rank,score,None
    r,g,b=(pixels[:,:,i] for i in range(3))
    votes={'h':int(((r>130)&(r>g*1.5)&(r>b*1.5)).sum()),
           'c':int(((g>65)&(g>r*1.4)&(g>b*1.4)).sum()),
           'd':int(((b>100)&(b>r*1.4)&(b>g*1.25)).sum())}
    suit=max(votes,key=votes.get)
    if votes[suit]>=12 and sum(v>8 for v in votes.values())==1:
        masks={'h':(r>130)&(r>g*1.5)&(r>b*1.5),'c':(g>65)&(g>r*1.4)&(g>b*1.4),
               'd':(b>100)&(b>r*1.4)&(b>g*1.25)}
        m=largest(masks[suit]);cx,cy,cw,ch=cv2.boundingRect(m)
        ref=cv2.imread(str(Path(__file__).parent.parent/'assets'/('suit_'+suit+'.png')),0)
        shape=normalized(m)
        expected=normalized(ref) if ref is not None else np.zeros((28,24),dtype=bool)
        similarity=(shape&expected).sum()/max(1,(shape|expected).sum())
        if suit=='c':
            small=cv2.imread(str(Path(__file__).parent.parent/'assets'/'suit_c_small.png'),0)
            if small is not None:
                alternative=normalized(small)
                similarity=max(similarity,(shape&alternative).sum()/max(1,(shape|alternative).sum()))
        if similarity<.64:
            return None,rank,score,None
    if votes[suit]<12 or sum(v>8 for v in votes.values())!=1:
        suit=None
        mask=largest(pixels.max(axis=2)<75)
        cx,cy,cw,ch=cv2.boundingRect(mask)
        if cw>4 and ch>6:
            reference=cv2.imread(str(Path(__file__).parent.parent/'assets'/'suit_s.png'),0)
            shape=normalized(mask)
            if reference is not None:
                expected=normalized(reference)
                union=(shape|expected).sum();similarity=(shape&expected).sum()/max(1,union)
                if similarity>.76:suit='s'
    card=rank+suit if suit and re.fullmatch(r'[2-9TJQKA]',rank) and score>=minimum_confidence else None
    return card,rank,score,suit


def rectangles(rgb,min_width=20,max_width=80):
    # Grey face backgrounds are included; card backs still fail rank/suit recognition.
    light=(rgb.min(axis=2)>115)&((rgb.max(axis=2).astype('int16')-rgb.min(axis=2))<35)
    contours,_=cv2.findContours(light.astype('uint8')*255,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    found=[]
    for c in contours:
        x,y,w,h=cv2.boundingRect(c)
        if min_width<w<max_width and 1.25<h/w<1.9:found.append([x,y,w,h])
    return found
