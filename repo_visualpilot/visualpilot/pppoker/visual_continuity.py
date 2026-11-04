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


# Conservative lab thresholds on RGB normalized to [0, 1]. These are not
# calibrated probabilities or semantic proof of a tournament's identity.
MAX_PATCH_ERROR = .045
MIN_DISTINCT_MARGIN = .025


def normalized_upper(frame, box):
    import cv2
    x,y,w,h=box
    region=frame[y:y+max(1,h//5),x:x+w]
    if region.size == 0 or float(region.std(axis=(0,1)).max()) < 20:
        return None
    resized=cv2.resize(region,(128,48),interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(resized.astype(np.float32)/255.,(3,3),.6)


def patch_error(a,b):
    if a is None or b is None:
        return float('inf')
    difference=np.abs(a-b).mean(axis=2)
    # A local change must not be diluted by a mostly unchanged background.
    return float(difference.reshape(4,12,8,16).mean(axis=(1,3)).max())


def tolerant_links(descriptors, boxes, previous):
    """Mutually unique matches, rejected when another table looks similar.

    previous entries: (identity record, normalized descriptor).
    Only consecutive accepted frames are supplied by the caller.
    """
    result={}
    for i,current in enumerate(descriptors):
        if current is None:
            continue
        scores=[]
        for j,(record,old) in enumerate(previous):
            ow,oh=record[1][2:];w,h=boxes[i][2:]
            sx,sy=w/ow,h/oh
            score=patch_error(current,old)
            if not (.5<=sx<=2 and .5<=sy<=2 and abs(sx/sy-1)<=.01):
                continue
            scores.append((score,j))
        scores.sort()
        if not scores or scores[0][0]>MAX_PATCH_ERROR:
            continue
        best,j=scores[0]
        old=previous[j][1]
        # Include visually similar competitors even if their geometry would
        # prevent a match: geometry must not manufacture visual uniqueness.
        alternatives=[patch_error(current,p[1]) for k,p in enumerate(previous) if k!=j]
        competitors=[patch_error(d,old) for k,d in enumerate(descriptors) if k!=i]
        if any(score < best+MIN_DISTINCT_MARGIN for score in alternatives+competitors):
            continue
        result[i]=j
    return result
