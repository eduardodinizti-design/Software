import re
from collections import OrderedDict
import hashlib
import cv2
import numpy as np
from ..training.perception import read_hero
from .actions import read_actions
from .buttons import parse_button
from .bounties import read_pko_bounties
from ..card_rank import rank_field
from ..replay.cards import face, rectangles
from ..replay.vision import classify, live_hand_id, box_of


NORMALIZED_TABLE_WIDTH = 755


class CachedReader:
    """Exact pixel cache of small OCR fields. Never caches a guessed result."""
    def __init__(self,reader):self.reader=reader;self.cache=OrderedDict()
    def detect(self,image):return self.reader.detect(image)
    def field(self,image):
        key=(image.shape,hashlib.blake2b(image.tobytes(),digest_size=16).digest())
        if key not in self.cache:
            self.cache[key]=self.reader.field(image)
            if len(self.cache)>256:self.cache.popitem(last=False)
        return self.cache[key]


def action_hint(rgb):
    h,w=rgb.shape[:2];p=rgb[int(h*.93):int(h*.98),int(w*.03):int(w*.30)].astype('int16')
    return bool(p.size and ((p[:,:,0]>120)&(p[:,:,0]>p[:,:,1]*1.4)&(p[:,:,0]>p[:,:,2]*1.4)).mean()>.15)


def read_table(reader,rgb):
    h,w=rgb.shape[:2]
    if not .40<w/h<.70:return dict(scene='unknown',status='pending',reason='Layout não suportado.')
    image=cv2.resize(rgb,(NORMALIZED_TABLE_WIDTH,round(h*NORMALIZED_TABLE_WIDTH/w)),interpolation=cv2.INTER_CUBIC)
    h,w=image.shape[:2];rows=reader.detect(image);scene=classify(rows,image)
    base=dict(scene=scene,hero=[],board=[],street=None,hand_id=live_hand_id(rows),actions=[],observed_actions=[],
              hero_buttons=[],action_pending=False,status='pending',pot=None,hero_stack=None,decision='Decisão ainda não implementada')
    if scene!='table':return dict(base,reason='Mesa encoberta ou tela não reconhecida.')
    base['observed_actions']=read_actions(rows,image)
    base['pko']=read_pko_bounties(rows,w,h)
    # Reuse the verified Hero reader but supply the already recognized rows.
    class View:
        def detect(self,_):return rows
        def field(self,crop):return reader.field(crop)
    hero=read_hero(View(),image,include_postflop=True)
    base['hero']=hero.get('cards',[])
    base['diagnostics']={'hero':hero.get('diagnostics',{}),'coordinate_space':'normalized_table','image_size':[w,h]}
    base['hero_confidence']=hero.get('confidence',[])
    base['evidence_size']=[w,h]
    base['evidence']={'hero':hero.get('evidence_boxes',[[int(w*.55),int(h*.78),int(w*.20),int(h*.12)]]),'board':[], 'observed_actions':[], 'actions':[[0,int(h*.93),w,int(h*.07)]]}
    if base['pko'].get('evidence_boxes'):
        base['evidence']['pko']=base['pko']['evidence_boxes']
    for b,t,score in rows:
        if base['hand_id'] and base['hand_id'] in t.replace(' ',''):base['evidence']['hand_id']=[box_of(b)]
    for action in base['observed_actions']:
        base['evidence']['observed_actions'].append(action['badge_box'])
        if action['player_box']:base['evidence']['observed_actions'].append(action['player_box'])
    base['hero_status']=hero['status'];base['hero_reason']=hero.get('reason','')
    board=image[int(h*.28):int(h*.65),int(w*.18):int(w*.90)]
    boxes=sorted(rectangles(board,25,115),key=lambda b:b[0])
    # Community cards are horizontally aligned near the table centre.
    # A visually estimated table crop can shift the card row slightly upward.
    # Keep complete card rectangles; recognition and duplicate checks still apply.
    boxes=[b for b in boxes if .36*h < b[1]+int(h*.28) < .48*h]
    class RankReader:
        def field(self,crop):return rank_field(reader,crop,.90)
    attempts=[face(RankReader(),board,b) for b in boxes]
    values=[a[0] for a in attempts]
    base['diagnostics']['board']=[dict(box=[b[0]+int(w*.18),b[1]+int(h*.28),b[2],b[3]],card=a[0],rank_candidate=a[1],rank_confidence=float(a[2]),suit_candidate=a[3]) for b,a in zip(boxes,attempts)]
    base['evidence']['board']=[[x+int(w*.18),y+int(h*.28),int(bw*.55),int(bh*.65)] for x,y,bw,bh in boxes] or [[int(w*.18),int(h*.38),int(w*.72),int(h*.12)]]
    base['board_status']='unknown'
    if len(values) in (3,4,5) and all(values) and len(set(values))==len(values):
        base['board']=values;base['street']={3:'flop',4:'turn',5:'river'}[len(values)]
        base['board_status']='read'
    else:
        base['board_uncertain']=True
        base['board_reason']='Cartas comunitárias não localizadas; pré-flop não comprovado.' if not boxes else 'Board incompleto ou ilegível.'
    for box,text,score in rows:
        if score<.90:continue
        cy=sum(p[1] for p in box)/4;cx=sum(p[0] for p in box)/4
        if cy>h*.90:
            button = parse_button(text,score,box_of(box))
            if button is not None:
                base['hero_buttons'].append(button)
            lower=text.lower()
            for action in ('fold','call','raise','check','bet'):
                if re.match(r'^'+action+r'(?:\b|\s|\d)',lower):base['actions'].append(text)
        if .34*h<cy<.58*h and .20*w<cx<.80*w and re.match(r'^pot\s*:',text,re.I):base['pot']=text;base['evidence']['pot']=[box_of(box)]
        if .87*h<cy<.93*h and .38*w<cx<.63*w and re.fullmatch(r'[\d.,]+\s*(?:BB)?',text):base['hero_stack']=text;base['evidence']['hero_stack']=[box_of(box)]
    base['action_pending']=action_hint(image) and bool(base['actions'])
    duplicates=len(set(base['hero']+base['board']))!=len(base['hero']+base['board'])
    if duplicates:
        base.update(hero=[],board=[],street=None,hero_status='pending',board_status='unknown',reason='Cartas conflitantes; leitura rejeitada.')
    else:
        base['status']='read' if len(base['hero'])==2 and base['street'] is not None else 'partial'
        base['reason']='' if base['status']=='read' else base.get('board_reason','Cartas do Hero pendentes.')
    return base
