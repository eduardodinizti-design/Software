import cv2
import numpy as np
import re


def rank_field(reader,crop,min_confidence=.95):
    raw,score=reader.field(crop)
    if score>=min_confidence and re.fullmatch(r'(?:[2-9TJQKA]|10)',raw.upper()):return raw,score
    gray=crop.min(2)
    votes=[]
    for scale in (.65,.80):
        threshold=float(np.percentile(gray,85))*scale
        ink=(gray<threshold).astype('uint8')
        n,labels,stats,_=cv2.connectedComponentsWithStats(ink)
        accepted=[]
        for i,(x,y,w,h,area) in enumerate(stats[1:],1):
            if area>=8 and x>0 and y>0 and x+w<gray.shape[1] and y+h<gray.shape[0]:accepted.append(i)
        if not accepted:continue
        mask=np.isin(labels,accepted).astype('uint8')*255
        x,y,w,h=cv2.boundingRect(mask)
        clean=cv2.copyMakeBorder(255-mask[y:y+h,x:x+w],8,8,8,8,cv2.BORDER_CONSTANT,value=255)
        value,confidence=reader.field(np.repeat(clean[:,:,None],3,axis=2))
        if re.fullmatch(r'(?:[2-9TJQKA]|10)',value.upper()) and confidence>=.90:votes.append((value.upper(),confidence))
    if len(votes)==2 and votes[0][0]==votes[1][0]:return votes[0][0],min(v[1] for v in votes)
    # A second, conservative route isolates a single interior glyph in luminance.
    # Coloured glyphs can lose their contour when RGB-min includes edge noise.
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    votes=[]
    for scale in (.55,.70):
        ink=(gray<float(np.percentile(gray,85))*scale).astype('uint8')
        n,labels,stats,_=cv2.connectedComponentsWithStats(ink)
        if n<2:continue
        index=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
        x,y,w,h,area=stats[index]
        if area<8 or x<=0 or y<=0 or x+w>=gray.shape[1] or y+h>=gray.shape[0]:continue
        mask=(labels[y:y+h,x:x+w]==index).astype('uint8')*255
        clean=cv2.copyMakeBorder(255-mask,8,8,8,8,cv2.BORDER_CONSTANT,value=255)
        value,confidence=reader.field(np.repeat(clean[:,:,None],3,axis=2))
        if re.fullmatch(r'(?:[2-9TJQKA]|10)',value.upper()) and confidence>=.95:
            votes.append((value.upper(),confidence))
    if len(votes)==2 and votes[0][0]==votes[1][0]:return votes[0][0],min(v[1] for v in votes)
    # Preserve antialiased edges: thresholding is used only to locate a glyph,
    # never as the pixels sent to OCR in this last conservative route.
    # Accept only agreement with the original candidate under two paddings.
    if re.fullmatch(r'(?:[2-9TJQKA]|10)', raw.upper()):
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        if count > 1:
            index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            x, y, w, h, area = stats[index]
            if area >= 8 and x > 0 and y > 0 and x+w < gray.shape[1] and y+h < gray.shape[0]:
                glyph = gray[y:y+h, x:x+w]
                votes = []
                for padding in (4, 8):
                    clean = cv2.copyMakeBorder(glyph, padding, padding, padding, padding,
                                               cv2.BORDER_CONSTANT, value=255)
                    value, confidence = reader.field(np.repeat(clean[:, :, None], 3, axis=2))
                    if value.upper() == raw.upper() and confidence >= max(.95, min_confidence):
                        votes.append(confidence)
                if len(votes) == 2:
                    return raw.upper(), min(votes)
    return raw,score if score>=min_confidence else 0.
