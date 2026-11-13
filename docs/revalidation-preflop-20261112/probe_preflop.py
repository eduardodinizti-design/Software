"""Passive semantic coverage probes; perfect structured inputs, no capture/input."""
import json, hashlib, collections, argparse
from copy import deepcopy
from preflop_advisor import PreflopAdvisor, infer_live_spot
from preflop_equity import hand_to_combos
from sizing import count_limpers

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pack', required=True)
parser.add_argument('--output', required=True)
args=parser.parse_args()
PATH=args.pack
pack=json.load(open(PATH)); a=PreflopAdvisor(pack)
positions={'hero':'BTN','v1':'UTG','v2':'HJ','v3':'CO','v4':'SB','v5':'BB',
           'v6':'UTG+1','v7':'UTG+2','v8':'LJ'}
def state(bets, hero_bet=0, stack=25, players=9):
    ps=dict(list(positions.items())[:players])
    return {'positions':ps,'seats':{s:{'occupied':True,'stack_bb':stack} for s in ps},
            'bets':[{'seat':s,'bet_bb':b} for s,b in bets.items()]+([{'seat':'hero','bet_bb':hero_bet}] if hero_bet else []),
            'pot':{'pot_bb':1.5+sum(bets.values())+hero_bet},
            'to_call':{'to_call_bb':max(0,max(bets.values(),default=0)-hero_bet)}}
cases={'unopened':state({}), 'two_limpers':state({'v1':1,'v2':1}),
       'one_open':state({'v1':2.5}),'open_two_calls':state({'v1':2.5,'v2':2.5,'v3':2.5}),
       'limp_raise':state({'v1':1,'v2':3}),
       'cold_3bet':state({'v1':2.5,'v2':8}),
       'hero_open_vs_3bet':state({'v2':8},hero_bet=2.5),
       'hero_3bet_vs_4bet':state({'v1':20},hero_bet=8),
       'open_short_villain':state({'v1':2.5}),'six_handed':state({},players=6)}
cases['open_short_villain']['seats']['v1']['stack_bb']=3

outputs={}
for name,st in cases.items():
    rows=[]
    for hand in pack['hands']:
        co=next(iter(hand_to_combos(hand)));hero=[str('23456789TJQKA'[r-2])+s for r,s in sorted(co)]
        r=a.advise_from_reading(st,hero)
        rows.append({'hand':hand,**{k:r.get(k) for k in ('status','reason','spot','node_id','validated','recommended','mix','sizing','stack_bucket','stack_borrowed_from','caveats')}})
    outputs[name]={'inferred':infer_live_spot(st),'limpers':count_limpers(st),'rows':rows,
                   'actions':dict(collections.Counter(r['recommended'] or r['reason'] for r in rows))}
def equivalent(x,y):
    return sum(all(u.get(k)==v.get(k) for k in ('node_id','recommended','mix','validated')) for u,v in zip(outputs[x]['rows'],outputs[y]['rows']))
summary={'pack':{'sha256':hashlib.sha256(open(PATH,'rb').read()).hexdigest(),'engineCommit':pack.get('engineCommit'),
    'nodes':len(pack['nodes']),'spots':dict(collections.Counter(n['spot'] for n in pack['nodes'])),
    'stacks':sorted({n['context']['stack'] for n in pack['nodes']}),'players':sorted({n['context']['players'] for n in pack['nodes']})},
    'cases':{n:{k:v for k,v in x.items() if k!='rows'} for n,x in outputs.items()},
    'identical_of_169':{'unopened_vs_two_limpers':equivalent('unopened','two_limpers'),
                        'open_vs_open_two_calls':equivalent('one_open','open_two_calls'),
                        'normal_vs_short_villain':equivalent('one_open','open_short_villain'),
                        'nine_vs_six_handed':equivalent('unopened','six_handed')},
    'stack_probes':{str(s):a.advise_from_reading(state({},stack=s),['As','Ah']) for s in (25,30,40,60,100)}}
print(json.dumps(summary,indent=2))
json.dump({'summary':summary,'outputs':outputs},open(args.output,'w'),indent=2)
