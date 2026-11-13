"""Passive probes for 5a14169. Synthetic cases are not Windows or production rates."""
import argparse, json, tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from strategy.action_sequence import replay
from strategy.scenarios import classify, from_table_state
from strategy.observer import ContinuousObserver
from decision_contract import evaluate
from preflop_advisor import PreflopAdvisor, infer_live_spot
from preflop_equity import hand_to_combos
from test_preflop_advisor import pack_with_node
from tournament_metrics import record_tournament_end
import operar_mesa
from raise_panel import is_shove_target, map_multiplier_to_preset
from bot_control import BotControl
from table_reading.tournament_end import detect_tournament_end

p=argparse.ArgumentParser();p.add_argument('--pack',required=True);args=p.parse_args()
pack=json.loads(Path(args.pack).read_text());a=PreflopAdvisor.from_file(args.pack)
positions={'hero':'BTN','v1':'UTG','v2':'HJ','v3':'CO','sb':'SB','bb':'BB','u1':'UTG+1','u2':'UTG+2','lj':'LJ'}
def state(bets):
    return {'positions':positions,'seats':{s:{'occupied':True,'stack_bb':25} for s in positions},
            'bets':[{'seat':s,'bet_bb':b} for s,b in dict(sb=.5,bb=1,**bets).items()],
            'pot':{'pot_bb':1.5+sum(bets.values())},'to_call':{'to_call_bb':max(bets.values(),default=1)}}
out={}
presets=[{'mult':m} for m in (2,2.5,3,4)]
out['non_allin_size_as_shove']={'planned_raise_bb':6,'hero_stack_bb':60,'target_mult':6,
       'nearest_preset':map_multiplier_to_preset(6,presets),
       'classified_as_shove':is_shove_target(6,presets),
       'scope':'Pure sizing predicate; no drag or input was sent'}
st=state({'v1':2.5,'v2':2.5,'v3':2.5})
for h in pack['hands']:
    cards=['23456789TJQKA'[r-2]+s for r,s in sorted(next(iter(hand_to_combos(h))))]
    adv=a.advise_from_reading(st,cards)
    if adv.get('recommended')=='call':
        out['multiway_contract']={'hand':h,'scenario':classify(from_table_state(st)),
             'inferred':infer_live_spot(st),'advice':adv,'contract':evaluate(adv,action='CALL',hero_cards=cards)};break
for h in pack['hands']:
    cards=['23456789TJQKA'[r-2]+s for r,s in sorted(next(iter(hand_to_combos(h))))]
    adv=a.advise_from_reading(state({'v1':1,'v2':1}),cards)
    if adv.get('recommended')=='fold' and any(m['action']=='raise' and m['frequency']>.5 for m in adv.get('mix',[])):
        out['iso_mix_mismatch']={'hand':h,'advice':adv};break
out['missing_bets']=classify(from_table_state(state({})))
out['empty_observation']=classify({})
st=state({'v1':2.5,'v2':2.5,'v3':2.5});o=ContinuousObserver()
before=o.observe(('t','h'),st);after=o.observe(('t','h'),state({'v1':2.5}))
out['observer_lost_callers']={'before':before,'after':after}
parts={'UTG':40,'CO':40,'BTN':40,'SB':40,'BB':40}
bl=[dict(position='SB',type='post_sb',amount_bb=.5),dict(position='BB',type='post_bb',amount_bb=1)]
def ev(pos,typ,amt):return dict(position=pos,type=typ,amount_bb=amt)
out['replay']={
 'out_of_turn':replay(bl+[ev('BTN','raise',2.5)],parts),
 'underpaid_call':replay(bl+[ev('UTG','call',.1)],parts),
 'invalid_minraise':replay(bl+[ev('UTG','raise',1.2)],parts),
 'non_allin_labeled_allin':replay(bl+[ev('UTG','all_in',5)],parts),
 'ante':replay(bl+[ev('UTG','post_ante',.1)],parts)}
class Adapter:
 def __init__(self):self.clicks=[]
 def move_to(self,*args):pass
 def click_once(self,*args):self.clicks.append(args)
class Engine:
 def capture_frame(self,**kw):return None,{}
adapter=Adapter();ctl=BotControl();ctl.pause()
with patch.object(operar_mesa,'_discover_rect',return_value=(0,0,400,600)),patch.object(operar_mesa.time,'sleep',lambda *_:None):
    closed=operar_mesa._close_tournament_table(np.zeros((600,400,3),np.uint8),(0,0,400,600),
            {'sair_box':[225,510,150,40]},1,adapter,Engine(),True)
out['close_while_paused_capture_failure']={'control':ctl.state,'fake_clicks':len(adapter.clicks),'closed':closed}
im=np.zeros((600,400,3),np.uint8);im[36:228,:]=[200,100,0]
im[510:550,25:175]=[100,220,0];im[510:550,225:375]=[100,220,0]
with patch('table_reading.tournament_end._ocr',return_value=''):
    out['synthetic_banner_without_text']=detect_tournament_end(im)
with tempfile.TemporaryDirectory() as d:
    out['itm_without_payouts']=record_tournament_end(ranking='40/272',path=str(Path(d)/'metrics.jsonl'))
    pa=pack_with_node();pb=pack_with_node();pb['nodes'][0]['freq']['raise']=[0.0]*169;pb['nodes'][0]['freq']['fold']=[1.0]*169
    fa=Path(d)/'a.json';fb=Path(d)/'b.json';fa.write_text(json.dumps(pa));fb.write_text(json.dumps(pb))
    m=PreflopAdvisor.from_files(fa,fb)
    out['default_merge_conflict']={'strict':m.strict,'collision':m.collisions,
        'answer':m.advise(hero_cards=['As','Ac'],hero_position='BTN',stack_bb=25)}
print(json.dumps(out,indent=2,default=str))
