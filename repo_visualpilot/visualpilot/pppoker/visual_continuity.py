"""Conservative consecutive-frame association across small crop-boundary changes.

Evidence is exact common pixels on an absolute sampling lattice, not position alone.
No semantic tournament identity or OCR authorization is implied.
"""
import numpy as np


def sample_upper(frame, box):
    x,y,w,h=box
    left=((x+7)//8)*8; top=((y+7)//8)*8
    return (left,top,frame[top:y+h//3:8,left:x+w:8].copy())


def matches(a, b, old_box, new_box):
    # Only small crop changes. Moving/resizing a table requires other evidence.
    if max(abs(u-v) for u,v in zip(old_box,new_box)) > max(old_box[2],new_box[2])*.05:
        return False
    ax,ay,aa=a; bx,by,bb=b
    left=max(ax,bx); top=max(ay,by)
    right=min(ax+aa.shape[1]*8,bx+bb.shape[1]*8)
    bottom=min(ay+aa.shape[0]*8,by+bb.shape[0]*8)
    if right<=left or bottom<=top:
        return False
    ac=aa[(top-ay)//8:(bottom-ay)//8,(left-ax)//8:(right-ax)//8]
    bc=bb[(top-by)//8:(bottom-by)//8,(left-bx)//8:(right-bx)//8]
    if ac.size < 300 or ac.size < .8*max(aa.size,bb.size):
        return False
    # Reject flat surfaces: matching felt color is not identity evidence.
    if float(ac.std(axis=(0,1)).max()) < 20:
        return False
    return np.array_equal(ac,bc)
