"""Observed PPPoker portrait layout; bottom-centre Hero, four-colour deck."""
from pathlib import Path
import cv2
import numpy as np
from ..replay.cards import normalized, rectangles, face
from ..card_rank import rank_field
from ..replay.vision import classify, live_hand_id


def suit(crop, diagnostics=None):
    pixels = crop.astype('int16')
    r,g,b = (pixels[:,:,i] for i in range(3))
    masks = {'s':pixels.max(2)<90, 'h':(r>130)&(r>1.5*g)&(r>1.5*b),
             'd':(b>100)&(b>1.4*r)&(b>1.25*g), 'c':(g>65)&(g>1.4*r)&(g>1.4*b)}
    scores = []
    for name, mask in masks.items():
        if mask.sum() < 12:continue
        shape = normalized(mask.astype('uint8')*255)
        reference = cv2.imread(str(Path(__file__).parents[1]/'assets'/('suit_'+name+'.png')),0)
        if reference is None:continue
        expected = normalized(reference)
        similarity = float((shape&expected).sum()/max(1,(shape|expected).sum()))
        if name == 'h':
            # Independent, intact board glyph; the legacy mask is fragmented.
            # Keep legacy compatibility, but require a stricter match for this
            # additional reference instead of relaxing the acceptance threshold.
            clean = cv2.imread(str(Path(__file__).parents[1]/'assets/suit_h_clean.png'),0)
            if clean is not None:
                expected = normalized(clean)
                clean_score = float((shape&expected).sum()/max(1,(shape|expected).sum()))
                if clean_score >= .85:
                    similarity = max(similarity, clean_score)
        scores.append((similarity,name))
    scores.sort(reverse=True)
    if diagnostics is not None:
        diagnostics.update(candidates=[dict(suit=name,similarity=score) for score,name in scores],method="four_colour_shape")
    if not scores or scores[0][0] < (.76 if scores[0][1]=='s' else .68) or (len(scores)>1 and scores[0][0]-scores[1][0]<.12):
        return None, 0.
    return scores[0][1],scores[0][0]


def read_hero(reader, rgb, include_postflop=False):
    h,w = rgb.shape[:2]
    if not .40 < w/h < .70:
        return dict(status='unsupported',reason='Layout fora do formato retrato validado.')
    # Normalize table size, not desktop coordinates.
    image = cv2.resize(rgb,(755,round(h*755/w)),interpolation=cv2.INTER_CUBIC)
    h,w = image.shape[:2]
    rows = reader.detect(image)
    if classify(rows,image) != 'table':
        return dict(status='pending',reason='Mesa não visível ou popup aberto.')
    hand_id = live_hand_id(rows)
    board = image[int(h*.28):int(h*.65),int(w*.20):int(w*.80)]
    if not include_postflop and any(face(reader,board,box)[0] for box in rectangles(board,25,115)):
        return dict(status='unsupported',reason='Cartas comunitárias visíveis: range pré-flop não aplicado.', hand_id=hand_id)
    hero_controls = any(min(p[1] for p in box)>h*.90 and score>=.85
                        and any(word in text.lower() for word in ('fold','call','raise','check','f/c'))
                        for box,text,score in rows)
    if not hero_controls and not include_postflop:
        return dict(status='pending',reason='Controles do Hero não confirmados; observação sem decisão.',hand_id=hand_id)
    # Overlapping white Hero cards form a single component. Opponent cards,
    # the board, buttons and nameplate are outside this area.
    left,top = int(w*.40),int(h*.76)
    crop = image[top:int(h*.90),left:int(w*.79)]
    candidates=[]
    for threshold in (165,100):
        light=(crop.min(2)>threshold)&((crop.max(2).astype('int16')-crop.min(2))<40)
        _,_,stats,_=cv2.connectedComponentsWithStats(light.astype('uint8'))
        parts=[list(map(int,b)) for b in stats[1:] if 65<b[3]<150 and .25<b[2]/b[3]<1.15 and b[4]/(b[2]*b[3])>.60]
        boxes=[p for p in parts if .95<p[2]/p[3]<1.15]
        for first in parts:
            for second in parts:
                x,y,cw,ch,area=first;xx,yy,ww,hh,aa=second
                # One-pixel overlap of component bounds is possible after resampling.
                if -1<=xx-(x+cw)<=8 and abs(y-yy)<=3 and abs(ch-hh)<=4 and .95<(xx+ww-x)/max(ch,hh)<1.15:
                    boxes.append([x,min(y,yy),xx+ww-x,max(ch,hh),area+aa])
        if len(boxes)==1:
            x,y,cw,ch,_=boxes[0];candidates=[(x+left,y+top,cw,ch)];break
    if len(candidates)!=1:
        return dict(status='pending',reason='Duas cartas do Hero não confirmadas.',hand_id=hand_id,
                    diagnostics=dict(stage='localization',candidate_count=len(candidates),search_box=[left,top,int(w*.79)-left,int(h*.90)-top],cards=[]))
    x,y,cw,ch = candidates[0]
    paper=image[y:y+ch,x:x+cw]
    neutral=paper[(paper.max(2).astype('int16')-paper.min(2))<40]
    level=float(np.percentile(neutral,80)) if neutral.size else 255.
    if 95<level<210:
        image=image.copy();image[y:y+ch,x:x+cw]=np.clip(paper.astype('float32')*(245/level),0,255).astype('uint8')
    cards=[];confidences=[];details=[];evidence=[]
    for cx in (x,x+round(cw*.34)):
        rank,confidence = rank_field(reader,image[y:y+round(ch*.36),cx:cx+round(ch*.28)])
        rank = 'T' if rank.upper()=='10' else rank.upper()
        suit_details={}
        symbol, similarity = suit(image[y+round(ch*.36):y+round(ch*.58),cx+round(ch*.035):cx+round(ch*.29)],suit_details)
        rank_box=[int(cx),int(y),round(ch*.28),round(ch*.36)]
        suit_box=[int(cx+round(ch*.035)),int(y+round(ch*.36)),round(ch*.29)-round(ch*.035),round(ch*.58)-round(ch*.36)]
        accepted=bool(rank in '23456789TJQKA' and len(rank)==1 and confidence>=.90 and symbol is not None)
        details.append(dict(index=len(details),rank_candidate=rank,rank_confidence=float(confidence),
                            suit_candidate=symbol,suit_similarity=float(similarity),suit_diagnostics=suit_details,accepted=accepted,
                            card=rank+symbol if accepted else None,rank_box=rank_box,suit_box=suit_box,
                            rejection=None if accepted else 'rank' if len(rank)!=1 or rank not in '23456789TJQKA' or confidence<.90 else 'suit'))
        evidence.append([int(cx),int(y),round(ch*.29),round(ch*.58)])
        if accepted:cards.append(rank+symbol);confidences.append(dict(rank=float(confidence),suit_shape=similarity))
    diagnostics=dict(stage='recognition',candidate_count=1,card_pair_box=[int(x),int(y),int(cw),int(ch)],cards=details)
    if len(cards)!=2:
        return dict(status='pending',reason='Valor ou naipe ilegível; decisão suspensa.',hand_id=hand_id,
                    diagnostics=diagnostics,evidence_boxes=evidence)
    if cards[0]==cards[1]:
        return dict(status='pending',reason='Cartas duplicadas na leitura; decisão suspensa.',hand_id=hand_id,diagnostics=diagnostics,evidence_boxes=evidence)
    return dict(status='read',cards=cards,hand_id=hand_id,confidence=confidences,diagnostics=diagnostics,
                evidence_boxes=[[int(cx),int(y),round(ch*.29),round(ch*.58)] for cx in (x,x+round(cw*.34))],
                layout='ppp-portrait-bottom-hero-four-colour',context_origin='screen')
