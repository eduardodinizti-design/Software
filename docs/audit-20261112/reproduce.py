import json
from unittest.mock import patch
import numpy as np
from preflop_context import PreflopAggressorTracker
from test_preflop_context import mk, HU_VS_OPEN
from test_registration import new_round, card, details
from reader_cache import ReaderCache
import assistir_mesa

out = {}
t = PreflopAggressorTracker()
pos = {'hero':'BB','a':'UTG','b':'BTN'}
for seat in ('a','b'):
    ctx = t.update(table_key='t', hand_key=1, has_board=False,
        table_state=mk(pos, [{'seat':seat,'bet_bb':2.5}], set(pos), {s:25 for s in pos}))
out['sequential_callers'] = ctx
t = PreflopAggressorTracker()
t.update(table_key='t', hand_key=1, has_board=False, table_state=HU_VS_OPEN)
out['unreadable_new_hand_board'] = t.update(table_key='t', hand_key=None,
    has_board=True, table_state=mk({'hero':'BB','v':'BTN'}, [], {'hero','v'}))

class Prop:
    status='COMPLETE_CANDIDATE'
    def __init__(self, x): self.box=(x,0,50,50)
frame = np.zeros((60,200,3),np.uint8)
calls=[]
def fake(crop, advisor, **kw):
    calls.append(kw['table_key'])
    return {'is_table':True}
with patch('assistir_mesa.advise_table',side_effect=fake), patch('assistir_mesa.detect_table_crops',side_effect=[[Prop(0),Prop(100)],[Prop(100)]]):
    first=assistir_mesa.advise_frame(frame,{'source_key':'w'},None)
    second=assistir_mesa.advise_frame(frame,{'source_key':'w'},None)
out['table_key_reassignment'] = {'first':[(r['box'],r['table_key']) for r in first], 'second':[(r['box'],r['table_key']) for r in second]}

r=new_round()
r.observe(card(),club='Karekas')
out['registration_wrong_target']=r.check_details(details(name='OTHER EVENT',club='Veneza'))
out['registration_wrong_target_reserve']=r.reserve()['flow_state']

calls=[]
def hud(crop,seats):
    calls.append(1)
    return {} if len(calls)>1 else {'v':{'stats':{'vpip':25},'confidence':'high'}}
c=ReaderCache(hud_every=1,hud_fn=hud)
c.huds(None,'t',['hero','v'])
out['cache_after_failed_refresh']=c.huds(None,'t',['hero','v'])
from test_raise_sequencer import World, WInput, _seq
w=World()
i=WInput(w)
s=_seq(w,i)
s.hand=None
r=s.run()
out['raise_unknown_hand']={'hand':s.hand,'clicks':len(i.clicks),'ok':r['ok'],'confirmed':r['confirmed']}
s._ra=lambda crop:{'status':'INVALID_CROP','buttons':[]}
out['raise_invalid_crop_verifier']=s._verify_bet(None,0)
print(json.dumps(out,indent=2))
