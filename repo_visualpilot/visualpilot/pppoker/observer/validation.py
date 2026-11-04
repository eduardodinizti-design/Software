"""Independent field freshness and confirmation; absent values never confirm cards."""
from copy import deepcopy
import re
import cv2
import numpy as np


def valid_cards(cards,n):
    return len(cards) in n and len(set(cards))==len(cards) and all(re.fullmatch(r'[2-9TJQKA][shdc]',c) for c in cards)


def confirmations(reading,previous=None):
    previous=previous or {};same_hand=bool(reading.get('hand_id')) and reading.get('hand_id')==previous.get('hand_id')
    blocked=set(reading.get('invalidated_fields',[]))
    hero=reading.get('hero',[]);board=reading.get('board',[]);street=reading.get('street')
    result={}
    for field,value,valid in [('hero',hero,valid_cards(hero,{2})),('board',board,valid_cards(board,{3,4,5}) and {3:'flop',4:'turn',5:'river'}.get(len(board))==street),('observed_actions',reading.get('observed_actions',[]),bool(reading.get('observed_actions')) and all(a.get('player_label') for a in reading['observed_actions']))]:
        signature=lambda xs:sorted((a['action'],a.get('player_label') or '') for a in xs) if field=='observed_actions' else xs
        confirmed=bool(valid and field not in blocked and same_hand and signature(value)==signature(previous.get(field,[])))
        state='confirmed' if confirmed else 'observed' if valid else 'pending'
        if field=='board' and not board and street=='preflop' and field not in blocked:state='not_dealt'
        result[field]=dict(state=state,confirmed=confirmed)
    return result


def patch(rgb,box,size):
    w,h=size;x,y,bw,bh=box;ih,iw=rgb.shape[:2]
    return rgb[max(0,round(y*ih/h)):min(ih,round((y+bh)*ih/h)),max(0,round(x*iw/w)):min(iw,round((x+bw)*iw/w))]


def changed(a,b):
    if a.shape!=b.shape or not a.size:return True
    # Compression/subpixel noise is tolerated, glyph changes are not.
    delta=np.abs(a.astype('int16')-b.astype('int16')).max(axis=2)
    return float((delta>24).mean())>.01


def validate_latest(reading,before,after):
    out=deepcopy(reading)
    if before.shape!=after.shape:
        invalid={'hero','board','observed_actions','actions','pot','hero_stack','hand_id','pko'}
    else:
        h,w=before.shape[:2];size=out.get('evidence_size',[w,h]);evidence=out.get('evidence',{})
        if not evidence:
            evidence={k:[box] for k,box in dict(hero=[w*.56,h*.79,w*.18,h*.10],board=[w*.18,h*.38,w*.72,h*.12],actions=[w*.02,h*.93,w*.96,h*.06]).items()}
        invalid={field for field,boxes in evidence.items() if any(changed(patch(before,box,size),patch(after,box,size)) for box in boxes)}
    if before.shape==after.shape and float((np.abs(before.astype('int16')-after.astype('int16')).max(axis=2)>40).mean())>.25:
        invalid.update(('hand_id','hero','board','observed_actions','actions','pot','hero_stack','pko'))
    if 'hand_id' in invalid:invalid.update(('hero','board','observed_actions','actions','pot','hero_stack','pko'))
    out['invalidated_fields']=sorted(invalid)
    for field in invalid:
        if field=='pko':out['pko']=dict(status='pending',seats=[],usable_for_strategy=False,reason='Região PKO mudou durante leitura.')
        if field in ('hero','board','observed_actions','actions'):out[field]=[]
        elif field in ('pot','hero_stack','hand_id'):out[field]=None
    if 'hero' in invalid:out.update(hero_status='pending',hero_reason='Região das cartas mudou durante leitura.')
    if 'board' in invalid:out.update(street=None,board_status='unknown')
    if 'actions' in invalid:
        out['action_pending']=False
        out['hero_buttons']=[]
    if any(f in invalid for f in ('hero','board')):out['status']='partial'
    if invalid:out['reason']='Atualizando: '+', '.join(sorted(invalid))+'. Outros campos preservados.'
    return out


def confirmation_previous(reading, previous, stamp, previous_stamp, window=10.0):
    """Comparison window is not the 5 s validity of the displayed observation."""
    if not previous or not 0 < stamp-previous_stamp < window:
        return None
    if not reading.get('hand_id') or reading.get('hand_id') != previous.get('hand_id'):
        return None
    return previous
