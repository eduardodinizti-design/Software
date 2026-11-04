"""Candidate bounty/stack association for the supplied PPPoker 8-seat PKO layout.

Consumes OCR rows, not strategy. No currency inference, no zero for missing data.
Geometry is a provisional profile; observations are not certified bounty inputs.
"""
import re
from ..replay.vision import box_of

SEATS={'top':(.51,.214),'left_upper':(.10,.377),'right_upper':(.90,.377),
       'left_middle':(.10,.607),'right_middle':(.90,.607),
       'left_lower':(.10,.778),'right_lower':(.90,.778),'hero':(.51,.899)}


def read_pko_bounties(rows, width, height):
    if not any(score>=.9 and re.search(r'\bPKO\b',text,re.I) for _,text,score in rows):
        return dict(status='unknown',seats=[],usable_for_strategy=False,reason='Tipo PKO não comprovado.')
    seats=[];evidence=[]
    def candidates(rect,predicate):
        x1,y1,x2,y2=rect;found=[]
        for poly,text,score in rows:
            x,y,w,h=box_of(poly);cx=(x+w/2)/width;cy=(y+h/2)/height
            if score>=.92 and x1<=cx<=x2 and y1<=cy<=y2 and predicate(text):
                found.append(dict(raw=text,confidence=float(score),box=[x,y,w,h]))
        return found[0] if len(found)==1 else None
    for seat,(cx,cy) in SEATS.items():
        rects=dict(name=(cx-.13,cy-.012,cx+.13,cy+.012),
                   stack=(cx-.13,cy+.012,cx+.13,cy+.037),
                   bounty=(cx-.13,cy-.108,cx+.13,cy-.080))
        # Store the whole profile patches, including pending fields, for invalidation.
        evidence.extend([[int(max(0,x1)*width),int(max(0,y1)*height),
                          int((min(1,x2)-max(0,x1))*width),int((min(1,y2)-max(0,y1))*height)]
                         for x1,y1,x2,y2 in rects.values()])
        name=candidates(rects['name'],lambda t:bool(re.search('[a-zA-Z]',t)) and not re.fullmatch(r'(fold|call|raise|check|bet)',t,re.I))
        stack=candidates(rects['stack'],lambda t:bool(re.fullmatch(r'\d+(?:[.,]\d{1,2})?\s*BB',t,re.I)))
        bounty=candidates(rects['bounty'],lambda t:bool(re.fullmatch(r'\d+(?:[.,]\d{1,2})?',t)))
        seats.append(dict(seat_id=seat,name=name,stack=stack,bounty=bounty,
            stack_bb=float(re.sub(r'\s*BB$','',stack['raw'],flags=re.I).replace(',','.')) if stack else None,
            bounty_display_value=float(bounty['raw'].replace(',','.')) if bounty else None,
            status='observed_candidate' if name and stack and bounty else 'pending'))
    hero=next(s for s in seats if s['seat_id']=='hero')
    for seat in seats:
        seat['hero_covers']= (hero['stack_bb']>=seat['stack_bb']) if (
            seat['seat_id']!='hero' and hero['stack_bb'] is not None and seat['stack_bb'] is not None) else None
    return dict(status='observed_candidates',layout='pppoker_pko_8seat_v228_candidate',
                seats=seats,evidence_boxes=evidence,bounty_unit='unknown',usable_for_strategy=False,
                reason='Validar perfil geométrico, leitura temporal e regra/unidade do bounty antes da estratégia.')
