"""Offline reference-range metrics and an exact toy river EV example.

This is a planning demonstration, not a postflop solver or an operator policy.
Only stdlib and Software's existing scalar evaluator are used. No OS input.
Run from a Software checkout with --ranges pointing to an NVT export.
"""
import argparse
from bisect import bisect_left
from itertools import combinations
import hashlib
import json
import math
from pathlib import Path
import random
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from preflop_equity import FULL_DECK, eval7, hand_to_combos, parse_card


def expand(classes,board=()):
    dead=set(board);pairs=[];weights=[]
    for hand,w in classes.items():
        if not math.isfinite(w) or not 0<w<=1:raise ValueError('Invalid action frequency')
        for pair in hand_to_combos(hand):
            if not pair & dead:pairs.append(tuple(sorted(pair)));weights.append(w)
    if not pairs:raise ValueError('Empty board-conditioned range')
    return pairs,weights


def make_sampler(pairs,weights):
    total=0.;cumulative=[]
    for w in weights:total+=w;cumulative.append(total)
    return lambda rng:pairs[min(bisect_left(cumulative,rng.random()*total),len(pairs)-1)]


def range_summary(classes,board):
    pairs,weights=expand(classes,board);mass=sum(weights)
    live=[c for c in FULL_DECK if c not in board]
    absolute=max(eval7(list(pair)+list(board)) for pair in combinations(live,2))
    categories={str(k):0. for k in range(9)};nuts=overpair=top_pair=0.
    for pair,w in zip(pairs,weights):
        score=eval7(list(pair)+list(board));categories[str(score[0])]+=w
        if score==absolute:nuts+=w
        if score[0]==1:
            if pair[0][0]==pair[1][0] and pair[0][0]>max(c[0] for c in board):overpair+=w
            if score[1]==max(c[0] for c in board) and any(c[0]==score[1] for c in pair):top_pair+=w
    return dict(legal_combos=len(pairs),weighted_combos=mass,
                distribution_normalization='Per-range weights after board removal; equity additionally conditions both private hands jointly.',
                category_mass={k:v/mass for k,v in categories.items()},
                absolute_current_nuts_mass=nuts/mass,overpair_mass=overpair/mass,
                top_pair_mass=top_pair/mass,
                nuts_definition='Maximum made-hand score among all legal hole combos on the CURRENT board; not a full future-equity tail.')


def simulate(left,right,board,n,seed,fixed_hero=None):
    lp,lw=expand(left,board);rp,rw=expand(right,board)
    ls=make_sampler(lp,lw);rs=make_sampler(rp,rw);rng=random.Random(seed)
    fixed=tuple(parse_card(c) for c in fixed_hero) if fixed_hero else None
    if fixed and (len(set(fixed))!=2 or set(fixed)&set(board)):raise ValueError('Invalid fixed hero')
    count=attempted=0;total=squares=0.
    while count<n:
        attempted+=1
        if attempted>n*200:raise ValueError('Incompatible ranges')
        hero=fixed or ls(rng);villain=rs(rng)
        if set(hero)&set(villain):continue
        dead=set(board)|set(hero)|set(villain)
        runout=rng.sample([c for c in FULL_DECK if c not in dead],5-len(board))
        hs=eval7(list(hero)+list(board)+runout);vs=eval7(list(villain)+list(board)+runout)
        value=1. if hs>vs else .5 if hs==vs else 0.
        total+=value;squares+=value*value;count+=1
    mean=total/n;se=math.sqrt(max(0.,(squares/n-mean*mean)/(n-1)))
    return dict(equity=mean,ci95_monte_carlo_only=[max(0.,mean-1.96*se),min(1.,mean+1.96*se)],
                samples=n,seed=seed,attempted_joint_deals=attempted,
                method='Independent weighted hole proposals, whole-pair collision rejection, uniform legal runout; win plus half ties',
                note='Showdown equity with no future betting. Not action EV, range correctness or solver validation.')


def river_example():
    board=[parse_card(c) for c in 'Kc 8s 3d Ts 2h'.split()]
    calls=[('Ah','Kd'),('Ad','Kh'),('Ac','Ks'),('Kh','Qd')]
    folds=[('Qs','Js'),('Qh','Jh'),('Qd','Jd'),('Js','9s'),('Jh','9h'),('9s','7s')]
    pot=25.;bet=pot*2/3;results=[]
    for hero in [('As','5s'),('6c','5c')]:
        h=[parse_card(c) for c in hero];hs=eval7(h+board)
        check=bet_ev=0.;accepted=0;fold_count=0
        for pair,action in [(p,'call') for p in calls]+[(p,'fold') for p in folds]:
            v=[parse_card(c) for c in pair]
            if set(h)&set(v) or set(v)&set(board):continue
            vs=eval7(v+board);equity=1. if hs>vs else .5 if hs==vs else 0.
            check+=equity*pot
            bet_ev+=pot if action=='fold' else equity*(pot+2*bet)-bet
            accepted+=1;fold_count+=action=='fold'
        results.append(dict(hero=list(hero),legal_opponent_combos=accepted,fold_probability=fold_count/accepted,
                            check_ev_bb=check/accepted,bet_two_thirds_ev_bb=bet_ev/accepted,
                            higher_ev_action='check' if check>bet_ev else 'bet_two_thirds'))
    assert abs(results[0]['check_ev_bb']-15.)<1e-8
    assert abs(results[0]['bet_two_thirds_ev_bb']-25/3)<1e-8
    assert results[0]['higher_ev_action']=='check' and results[1]['higher_ev_action']=='bet_two_thirds'
    return dict(kind='SYNTHETIC_FIXED_RIVER_RESPONSE_MODEL',board=['Kc','8s','3d','Ts','2h'],pot_before_bet_bb=pot,
                bet_bb=bet,opponent_call_combos=[list(p) for p in calls],opponent_fold_combos=[list(p) for p in folds],
                combo_weights=1.,results=results,bluff_break_even_fold_probability=bet/(pot+bet),
                assumptions=['Villain already checked; hero is last to act.', 'All remaining Kx combos call and the six listed missed draws fold.',
                             'No check-raise, rake, side pot, ICM or bounty. Hero has enough stack.',
                             'This node is supplied in isolation. It does not prove either hero hand should reach this river through two prior barrels.'],
                meaning='Exact ten-combo arithmetic, not a population measurement or a solved strategy.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ranges',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--samples',type=int,default=20000)
    args=p.parse_args()
    if args.samples<100:raise ValueError('At least 100 samples')
    raw=args.ranges.read_bytes();pack=json.loads(raw);library={}
    for hero,spot,vs,action in [('BTN','open_raise',[],'raise'),('UTG','open_raise',[],'raise'),('BB','vs_open',['BTN'],'call'),('BB','vs_open',['UTG'],'call')]:
        nodes=[n for n in pack['nodes'] if n.get('hero')==hero and n.get('spot')==spot and n.get('vs',[])==vs
               and all(n['context'].get(k)==v for k,v in dict(mode='chip_ev',stage='mid',players=9,stack=25).items())]
        if len(nodes)!=1:raise ValueError('Expected exactly one public reference node '+str((hero,spot,vs)))
        node=nodes[0];weights={h:node['freq'][action][i] for i,h in enumerate(pack['hands']) if node['freq'][action][i]>0}
        identity=hero+'_'+('open' if not vs else 'call_vs_'+vs[0])+'_25'
        pairs,w=expand(weights)
        library[identity]=dict(id=identity,node_id=node['id'],selected_action=action,context=node['context'],
                              class_frequencies=weights,nonzero_classes=len(weights),physical_combos=len(pairs),weighted_combos=sum(w),
                              source_marked_validated=node.get('validated') is True,independent_validation=False)
    cases=[]
    for index,(opener,board,hero_cards) in enumerate([
        ('BTN','As 7d 2c',['Ah','Qh']),('BTN','9s 8s 7d',['Jc','Td']),
        ('BTN','7s 7h 2d',['8c','8d']),('UTG','As 7d 2c',['Kh','Kd'])]):
        left=library[opener+'_open_25'];right=library['BB_call_vs_'+opener+'_25'];public=[parse_card(c) for c in board.split()]
        eq=simulate(left['class_frequencies'],right['class_frequencies'],public,args.samples,1200+index)
        fixed=simulate(left['class_frequencies'],right['class_frequencies'],public,args.samples,2200+index,hero_cards)
        cases.append(dict(id=opener+'_vs_BB_'+board.replace(' ','_'),hero_position=opener,villain_position='BB',
                          table_players=9,postflop_players=2,board=board.split(),hero_example=hero_cards,
                          hero_range_id=left['id'],villain_range_id=right['id'],
                          hero_range_summary=range_summary(left['class_frequencies'],public),
                          villain_range_summary=range_summary(right['class_frequencies'],public),
                          range_vs_range=eq,hero_exact_vs_villain=fixed))
    digest=hashlib.sha256(raw).hexdigest()
    public_match=digest=='c8fc3f0716df16fdeb2cff509814e3ca3c1ec31c05d479da2122db3ec531fcdc'
    source=dict(repository='eduardodinizti-design/Software' if public_match else None,
                commit='8c7f585cabf0b53217c9001988de52c387fb5153' if public_match else None,
                path='strategy_sources/nvt-356340d/nvt-ranges-validados.json' if public_match else None,
                public_snapshot_matched=public_match,sha256=digest,
                engine_commit=pack.get('engineCommit'),generated_at=pack.get('generatedAt'),
                note='Public historical NVT snapshot' if public_match else 'User-supplied export; repository/commit provenance not asserted.')
    source['limitations']='Not proof of the ranges loaded by Windows. Open size, antes and opponent response policies are not established by this export.'
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'ranges-referencia.json').write_text(json.dumps(dict(source=source,ranges=library),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    result=dict(source=source,scope='Offline teaching examples: weighted ranges, blockers, current made-hand distribution and showdown equity. No recommended c-bet or solved full line.',
                cases=cases,river_ev_example=river_example(),solver_validated=False,pppoker_windows_validation=False)
    (args.out/'demonstracoes-calculadas.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(cases=len(cases),samples_per_estimate=args.samples,
                        ranges={k:dict(classes=v['nonzero_classes'],weighted_combos=v['weighted_combos']) for k,v in library.items()},
                        results=[dict(case=c['id'],range_equity=c['range_vs_range']['equity'],hero_equity=c['hero_exact_vs_villain']['equity']) for c in cases]),ensure_ascii=False))


if __name__=='__main__':main()
