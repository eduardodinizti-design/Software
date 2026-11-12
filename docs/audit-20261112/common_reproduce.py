"""Run from either audited repository root with PYTHONPATH=. (no real input)."""
import json
from preflop_context import PreflopAggressorTracker
from test_preflop_context import mk, HU_VS_OPEN
from test_registration import new_round, card, details
from test_raise_sequencer import World, WInput, _seq

out = {}
t = PreflopAggressorTracker()
pos = {'hero': 'BB', 'a': 'UTG', 'b': 'BTN'}
for seat in ('a', 'b'):
    ctx = t.update(table_key='t', hand_key=1, has_board=False,
                   table_state=mk(pos, [{'seat': seat, 'bet_bb': 2.5}], set(pos),
                                  {s: 25 for s in pos}))
out['sequential_callers'] = ctx
t = PreflopAggressorTracker()
t.update(table_key='t', hand_key=1, has_board=False, table_state=HU_VS_OPEN)
out['unreadable_new_hand_board'] = t.update(
    table_key='t', hand_key=None, has_board=True,
    table_state=mk({'hero': 'BB', 'v': 'BTN'}, [], {'hero', 'v'}))
r = new_round()
r.observe(card(), club='Karekas')
out['registration_wrong_target'] = r.check_details(
    details(name='OTHER EVENT', club='Veneza'))['flow_state']
out['registration_wrong_target_reserve'] = r.reserve()['flow_state']
w = World()
i = WInput(w)
s = _seq(w, i)
s.hand = None
r = s.run()
out['raise_unknown_hand'] = dict(hand=s.hand, clicks=len(i.clicks),
                                ok=r['ok'], confirmed=r['confirmed'])
s._ra = lambda crop: {'status': 'INVALID_CROP', 'buttons': []}
out['raise_invalid_crop_verifier'] = s._verify_bet(None, 0)
print(json.dumps(out, indent=2))
