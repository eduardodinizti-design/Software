"""Offline counterexamples. No capture, input, network or real session data.

Exit 1 means at least one decision violates the stated analytical expectation.
Run each repository in a separate process to keep imports and globals isolated.
"""
import argparse
import inspect
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
p.add_argument('--kind',choices=['software','clone','central'],required=True)
args=p.parse_args();root=args.root.resolve();sys.path.insert(0,str(root))
sha=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
cases=[]

if args.kind=='software':
    from postflop_advisor import advise_postflop
    def table(pot=30,call=10,stack=100):
        return {'pot':{'pot_bb':pot},'to_call':{'to_call_bb':call},
                'seats':{'hero':{'occupied':True,'in_hand':True,'stack_bb':stack},
                         'v':{'occupied':True,'in_hand':True,'stack_bb':100}}}
    s=table();hero=['As','Ad'];board=['Ac','Kh','7d','2c','3s']
    for i in range(7):s['seats']['folded'+str(i)]={'occupied':True,'in_hand':False,'stack_bb':100}
    if 'villains' in inspect.signature(advise_postflop).parameters:
        a=advise_postflop(s,hero,board,pot_type='single_raised',villain_range=['KK'],iters=100)
        hu=advise_postflop(s,hero,board,pot_type='single_raised',villain_range=['KK'],villains=1,iters=100)
        cases.append(dict(id='occupied_seats_are_not_active_opponents',
            input=dict(hero=hero,board=board,occupied=9,active_opponents=1,villain_range=['KK'],pot=30,to_call=10),
            expected='Never fold: every eligible KK combo loses to the hero set of aces.',
            actual={k:a.get(k) for k in ('recommended','equity','opponents')},
            with_explicit_single_opponent={k:hu.get(k) for k in ('recommended','equity','opponents')},
            satisfies=a.get('recommended')!='fold'))
    s=table();hero=['7h','7d'];board=['Ac','Ad','7c','2d','3s']
    a=advise_postflop(s,hero,board,pot_type='three_bet',villain_range=['AA'],iters=100)
    cases.append(dict(id='three_bet_branch_ignores_supplied_range',
        input=dict(hero=hero,board=board,villain_range=['AA'],pot=30,to_call=10),
        expected='Fold: full house always loses to the only eligible AA combo (quads).',
        actual={k:a.get(k) for k in ('recommended','equity','made','sizing')},
        satisfies=a.get('recommended')=='fold'))
    s=table(pot=20,call=10,stack=100)
    a=advise_postflop(s,['As','Ad'],['Ac','Kh','7d','2c','3s'],pot_type='single_raised',villain_range=['KK'],iters=100)
    cases.append(dict(id='mdf_uses_pot_before_opponent_bet',
        input=dict(pot_including_bet=20,opponent_bet=10,to_call=10,hero_already_bet_this_street=0),
        expected_mdf=.5,actual={k:a.get(k) for k in ('mdf','pot_odds')},
        satisfies=abs(a.get('mdf',0)-.5)<1e-6))
    hero=['2c','3d'];board=['As','Ks','Qs','Js','Ts'];s=table(pot=1010,call=1000,stack=5000)
    a=advise_postflop(s,hero,board,pot_type='single_raised',villain_range=['AA'],iters=100)
    cases.append(dict(id='guaranteed_chop_positive_call_ev',
        input=dict(hero=hero,board=board,pot_including_villain_bet=1010,to_call=1000,range=['AA']),
        exact_equity=.5,exact_call_ev_bb=5.,expected='Call is strictly better than fold; no possible losing runout on this royal board.',
        actual={k:a.get(k) for k in ('recommended','equity','pot_odds')},
        satisfies=a.get('recommended')=='call'))
elif args.kind=='clone':
    from postflop_policy import advise
    from preflop_equity import hand_to_combos
    c=dict(hero=['2c','3d'],board=['As','Ks','Qs','Js','Ts'],mode='chip_ev',stage='mid',
        hero_position='BTN',villain_position='BB',pot_type='single_raised',opponents=1,
        aggressor='villain',pot=1010.,to_call=1000.,hero_stack=5000.,villain_stack=4000.)
    a=advise(c,[(combo,1.) for combo in hand_to_combos('AA')])
    cases.append(dict(id='guaranteed_chop_positive_call_ev',input=c,
        exact_equity=.5,exact_call_ev_bb=5.,expected='Call; exact guaranteed split on a royal board.',
        actual={k:a.get(k) for k in ('recommended','equity','pot_odds','checkdown_call_ev_bb','conservative_call_ev_proxy_bb')},
        satisfies=a.get('recommended')=='call'))
else:
    from visualpilot.lab.postflop import compare_actions,expand_range
    hero=['2c','3d'];board=['As','Ks','Qs','Js','Ts']
    r=compare_actions(hero,board,expand_range({'AA':1.},dead=hero+board),pot=1010,stack=5000,to_call=1000)
    cases.append(dict(id='guaranteed_chop_positive_call_ev',result=r,
        expected='Call EV=+5BB, fold EV=0 under exact river enumeration.',
        satisfies=any(x['action']=='call' and abs(x['ev']-5)<1e-8 for x in r['comparisons'])))

result=dict(scope='Synthetic analytical states; no solver certification or PPPoker test.',
            kind=args.kind,commit=sha,cases=cases,violations=sum(not c['satisfies'] for c in cases))
print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(bool(result['violations']))
