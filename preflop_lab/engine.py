"""Counterfactual preflop EV with joint ranges, responses and postflop rollouts.

This is a finite, fixed-opponent-model calculation. It is not CFR/Nash/HRC.
Preflop future hero call/fold nodes are fitted on a training deal set; action
values are measured on disjoint held-out deals. Postflop actors only see their
own hole cards and the board already dealt, never a sampled opponent/runout.
Postflop continuation is a disclosed one-bet-per-street behavioural model.
"""
import hashlib
import json
import math
import time
import numpy as np

from . import VERSION
from .cards import card_id, hand_class, deal, evaluate, made_features
from .payouts import settle, bounty_awards

EPS=1e-8
ORDER=('UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB','BB')
POST_ORDER=('SB','BB','UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN')


def validate(case):
    players=case.get('players') or []
    if not 2<=len(players)<=9 or players[0].get('role')!='hero':
        raise ValueError('Two to nine players, hero first, are required.')
    positions=[p.get('position') for p in players]
    if len(set(positions))!=len(positions) or any(p not in ORDER for p in positions):
        raise ValueError('Unique known positions required.')
    for p in players:
        for key in ('stack_bb','bet_bb'):
            v=p.get(key)
            if type(v) not in (int,float) or not math.isfinite(v) or v<0:
                raise ValueError('Finite nonnegative stack/contribution required.')
        if p['stack_bb']+p['bet_bb']<=0:raise ValueError('Empty player stack.')
        bounty=p.get('immediate_bounty_bb',0.)
        if type(bounty) not in (int,float) or not math.isfinite(bounty) or bounty<0:
            raise ValueError('Immediate cash head must be finite and nonnegative.')
    if players[0]['stack_bb']<=0:raise ValueError('Hero has no decision chips.')
    pot=case.get('pot_bb')
    if type(pot) not in (int,float) or not math.isfinite(pot) or pot<sum(p['bet_bb'] for p in players)-EPS:
        raise ValueError('Pot must include every current contribution.')
    if case.get('mode','chip_ev')!='chip_ev':
        raise ValueError('This rollout is chip-EV plus declared immediate cash; no invented payout ICM.')
    for p in players[1:]:
        if not isinstance(p.get('range'),dict) or not p['range']:
            raise ValueError('Every opponent needs an explicit arrival range.')
        response=p.get('response') or {}
        for name in ('call','raise'):
            if not isinstance(response.get(name),dict):raise ValueError('Explicit response frequencies required.')
        for hand in set(response['call'])|set(response['raise']):
            c,r=response['call'].get(hand,0),response['raise'].get(hand,0)
            if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in (c,r)) or c+r>1+EPS:
                raise ValueError('Invalid response probabilities.')
    return case


def actions(case):
    """Actual total raise sizes; no blind-depth veto or implicit all-in."""
    players=case['players'];own=players[0]['bet_bb'];cap=own+players[0]['stack_bb']
    top=max(p['bet_bb'] for p in players);call=max(0,top-own)
    out=[dict(id='fold',action='fold',raise_to_bb=None)] if call>EPS else []
    out.append(dict(id='call' if call>EPS else 'check',action='call' if call>EPS else 'check',raise_to_bb=None))
    previous=case.get('last_full_raise_bb',max(1.,top-own))
    for target in case.get('raise_sizes_bb') or []:
        if type(target) not in (int,float) or not math.isfinite(target) or target<=top+EPS or target>cap+EPS:
            continue
        if target-top<previous-EPS and abs(target-cap)>EPS:continue
        if not any(a['raise_to_bb'] is not None and abs(a['raise_to_bb']-target)<EPS for a in out):
            out.append(dict(id='raise_to_%g'%target,action=case.get('raise_action','raise'),raise_to_bb=float(target),all_in=abs(target-cap)<EPS))
    if cap>top+EPS and case.get('include_shove',True) and not any(a.get('all_in') for a in out):
        out.append(dict(id='all_in',action='all_in',raise_to_bb=float(cap),all_in=True))
    return out


def _event_groups(paid,active,rows):
    # Entire key is preflop-public money/participants. No sampled private cards.
    return np.column_stack((np.rint(paid[rows]*10000).astype(np.int64),active[rows].astype(np.int64)))


def _key(row):return ','.join(map(str,row.tolist()))


def _preflop(case,holes,action,rng,future=None):
    n,p,_=holes.shape
    initial=np.asarray([v['bet_bb'] for v in case['players']],float)
    caps=initial+np.asarray([v['stack_bb'] for v in case['players']],float)
    paid=np.broadcast_to(initial,(n,p)).copy();active=np.ones((n,p),bool)
    pending=np.zeros((n,p),bool);raises=np.zeros(n,dtype=np.int16);events=[];unseen=0
    if action['action']=='fold':active[:,0]=False;return paid,active,events,unseen
    if action['raise_to_bb'] is None:paid[:,0]=np.minimum(caps[0],np.max(paid,axis=1))
    else:paid[:,0]=action['raise_to_bb'];pending[:,1:]=True;raises[:]=1
    if action['raise_to_bb'] is None:
        for j,pl in enumerate(case['players'][1:],1):pending[:,j]=pl.get('yet_to_act',False)
    positions=[pl['position'] for pl in case['players']]
    circular=sorted(range(p),key=lambda j:(ORDER.index(positions[j])-ORDER.index(positions[0]))%9)
    circular=circular[1:]+[0]
    klass=[[hand_class(pair) for pair in holes[:,j]] for j in range(1,p)]
    response=[]
    for j,pl in enumerate(case['players'][1:],1):
        spec=pl['response'];hh=klass[j-1]
        response.append((np.asarray([spec['call'].get(h,0.) for h in hh]),
                         np.asarray([spec['raise'].get(h,0.) for h in hh]),
                         float(spec.get('reference_price_bb',2.5))))
    max_raises=int(case.get('preflop_raise_cap',3))
    last_full_raise=np.full(n,float(case.get('last_full_raise_bb',1.)))
    if action['raise_to_bb'] is not None:
        last_full_raise[:]=action['raise_to_bb']-max(initial)
    rights=pending.copy()
    for _ in range(max_raises+2):
        for j in circular:
            pending&=active&(paid<caps-EPS)
            pending[active.sum(axis=1)<=1,:]=False
            rows=np.flatnonzero(pending[:,j])
            if not len(rows):continue
            pending[rows,j]=False
            had_raise_right=rights[rows,j].copy();rights[rows,j]=False
            top=np.max(paid[rows],axis=1);due=top-paid[rows,j]
            if j==0:
                keys=_event_groups(paid,active,rows)
                if future is None:
                    events.append((rows.copy(),keys,(-(paid[rows,0]-initial[0])).copy()))
                    will_call=np.ones(len(rows),bool)
                else:
                    labels=[future.get(_key(row)) for row in keys]
                    unseen+=sum(x is None for x in labels)
                    # Unseen public branches are marked; a missing branch cannot
                    # manufacture a positive held-out continuation value.
                    will_call=np.asarray([bool(x) for x in labels]) | (due<=EPS)
                active[rows[~will_call],0]=False
                paid[rows[will_call],0]=np.minimum(caps[0],top[will_call])
                continue
            cf,rf,reference=response[j-1]
            # NVT vectors remain explicit response priors. Price attenuation is
            # a declared behaviour-model assumption, not a solved response.
            scale=np.minimum(1.,reference/np.maximum(due,.01))
            # The explicit cash-model value core does not fold AA/KK merely
            # because a reference node had a smaller price. Model, not proof.
            value_core=np.asarray([klass[j-1][r] in ('AA','KK') for r in rows])
            scale=np.where(value_core,1.,scale)
            cp=cf[rows]*np.sqrt(scale);rp=rf[rows]*scale
            can_raise=(raises[rows]<max_raises)&(caps[j]>top+EPS)&had_raise_right
            cp+=np.where(can_raise,0,rp);rp=np.where(can_raise,rp,0)
            roll=rng.random(len(rows));reraise=roll<rp
            call=(roll<rp+cp)| (due<=EPS)
            fold=~call
            active[rows[fold],j]=False
            rr=rows[call&~reraise]
            paid[rr,j]=np.minimum(caps[j],np.max(paid[rr],axis=1))
            rr=rows[reraise]
            if len(rr):
                old=np.max(paid[rr],axis=1)
                target=np.minimum(caps[j],np.maximum(old+last_full_raise[rr],old*float(case.get('response_raise_multiplier',3.))))
                full=target-old>=last_full_raise[rr]-EPS
                last_full_raise[rr[full]]=target[full]-old[full]
                paid[rr,j]=target;raises[rr]+=1
                pending[rr,:]=active[rr,:]&(paid[rr,:]<caps-EPS)
                pending[rr,j]=False
                rights[rr[full],:]=active[rr[full],:]&(paid[rr[full],:]<caps-EPS)
                rights[rr,j]=False
        if not pending.any():break
    if pending.any():raise ArithmeticError('Preflop betting did not settle within its declared raise cap.')
    return paid,active,events,unseen


def _postflop(case,holes,board,paid,active,rng):
    caps=np.asarray([v['bet_bb']+v['stack_bb'] for v in case['players']],float)
    n,p,_=holes.shape;initial=np.asarray([v['bet_bb'] for v in case['players']],float)
    dead=case['pot_bb']-initial.sum()
    order=sorted(range(p),key=lambda j:POST_ORDER.index(case['players'][j]['position']))
    tuning=case.get('continuation') or {}
    aggression=float(tuning.get('aggression',1.));calls=float(tuning.get('call_scale',1.))
    for street in (3,4,5):
        category,top_pair,draw=made_features(holes,board[:,:street])
        street_paid=np.zeros((n,p));bet_made=np.zeros(n,bool)
        pending=active&(paid<caps-EPS)
        pending[(active.sum(axis=1)<2)|(((caps-paid>EPS)&active).sum(axis=1)<2),:]=False
        for _ in range(2):  # exactly one bet per street; earlier checks may face it
            for j in order:
                rows=np.flatnonzero(pending[:,j]&active[:,j]&(paid[:,j]<caps[j]-EPS))
                if not len(rows):continue
                pending[rows,j]=False
                due=np.max(street_paid[rows],axis=1)-street_paid[rows,j]
                pot=dead+paid[rows].sum(axis=1)
                facing=due>EPS
                small=due/np.maximum(pot,.01)<=.25
                made=category[rows,j];tp=top_pair[rows,j];dr=draw[rows,j]
                cp=np.where(made>=2,1.,np.where(tp,np.where(small,.95,.7),
                         np.where(made==1,np.where(small,.55,.18),np.where(dr,.65,.025))))
                cp=np.minimum(1.,cp*calls)
                call=rng.random(len(rows))<cp
                folded=rows[facing&~call];active[folded,j]=False
                paid_rows=rows[facing&call]
                amount=np.minimum(caps[j]-paid[paid_rows,j],due[facing&call])
                paid[paid_rows,j]+=amount;street_paid[paid_rows,j]+=amount
                open_rows=rows[~facing&~bet_made[rows]]
                if len(open_rows):
                    live_money=(active[open_rows]&(paid[open_rows]<caps-EPS)).sum(axis=1)>=2
                    made=category[open_rows,j];tp=top_pair[open_rows,j];dr=draw[open_rows,j]
                    villains=np.maximum(1,active[open_rows].sum(axis=1)-1)
                    bp=np.where(made>=2,.8,np.where(tp,.55,np.where(dr,.45,np.where(made==1,.12,.10/villains))))
                    wager=(rng.random(len(open_rows))<np.minimum(1.,bp*aggression))&live_money
                    rr=open_rows[wager]
                    if len(rr):
                        amount=(dead+paid[rr].sum(axis=1))*({3:1/3,4:.5,5:2/3}[street])
                        other=np.where(active[rr],caps-paid[rr],0.);other[:,j]=0
                        amount=np.minimum(amount,np.max(other,axis=1))
                        amount=np.minimum(amount,caps[j]-paid[rr,j])
                        paid[rr,j]+=amount;street_paid[rr,j]+=amount;bet_made[rr]=True
                        pending[rr]=active[rr]&(paid[rr]<caps-EPS);pending[rr,j]=False
                pending[active.sum(axis=1)<=1,:]=False
        if pending.any():raise ArithmeticError('Postflop continuation did not settle.')
    return paid,active


def simulate(case,hero,action,samples,seed,*,future=None):
    validate(case)
    holes,board,dealing=deal(hero,[p['range'] for p in case['players'][1:]],samples,seed)
    rng=np.random.default_rng(seed^0x51A7)
    paid,active,events,unseen=_preflop(case,holes,action,rng,future)
    paid,active=_postflop(case,holes,board,paid,active,rng)
    public=np.broadcast_to(board[:,None,:],(samples,len(case['players']),5))
    ranks=evaluate(np.concatenate((holes,public),axis=2))
    initial=np.asarray([p['bet_bb'] for p in case['players']],float)
    caps=initial+np.asarray([p['stack_bb'] for p in case['players']],float)
    awards=settle(paid,active,ranks,case['pot_bb']-initial.sum())
    heads=np.asarray([p.get('immediate_bounty_bb',0.) for p in case['players']],float)
    bounties=bounty_awards(paid,active,ranks,awards,caps,heads)
    values=awards[:,0]-(paid[:,0]-initial[0])+bounties[:,0]
    if action['action']=='fold':values[:]=0.
    return values,events,dict(dealing=dealing,unseen_future_policy_visits=unseen,
                              mean_future_investment_bb=float((paid[:,0]-initial[0]).mean()),
                              mean_immediate_bounty_bb=float(bounties[:,0].mean()))


def fit_future(values,events,min_observations=16):
    """Backward call/fold best responses at public preflop nodes, training only."""
    values=values.copy();policy={}
    for rows,keys,folds in reversed(events):
        unique,inverse=np.unique(keys,axis=0,return_inverse=True)
        for j,row in enumerate(unique):
            rr=rows[inverse==j];fold=float(folds[inverse==j][0])
            call=bool(values[rr].mean()>=fold) if len(rr)>=min_observations else False
            policy[_key(row)]=call
            if not call:values[rr]=fold
    return policy,values


def solve(case,hero,*,train_samples=1024,evaluation_samples=4096,seed=1):
    """Measure each candidate on disjoint train/evaluation deals; retain errors."""
    started=time.perf_counter();validate(case);candidates=actions(case);results=[]
    for a in candidates:
        if a['action']=='fold':
            results.append(dict(a,ev_bb=0.,stderr_bb=0.,ci95_bb=[0.,0.],samples=evaluation_samples,training_ev_bb=0.,future_nodes=0))
            continue
        train,events,_=simulate(case,hero,a,train_samples,seed,future=None)
        future,training=fit_future(train,events)
        heldout,_,detail=simulate(case,hero,a,evaluation_samples,seed+1000003,future=future)
        mean=float(heldout.mean());se=float(heldout.std(ddof=1)/math.sqrt(len(heldout)))
        results.append(dict(a,ev_bb=mean,stderr_bb=se,ci95_bb=[mean-1.96*se,mean+1.96*se],
                            samples=len(heldout),training_ev_bb=float(training.mean()),future_nodes=len(future),detail=detail))
    best=max(results,key=lambda a:a['training_ev_bb'])
    eval_best=max(results,key=lambda a:a['ev_bb'])
    alternatives=[r for r in results if r is not best]
    clear=all(best['ci95_bb'][0]>r['ci95_bb'][1] for r in alternatives)
    canonical=json.dumps(case,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return dict(version=VERSION,case_id=case.get('id'),context_sha256=hashlib.sha256(canonical).hexdigest(),
                hero_cards=hero,hand=hand_class([card_id(c) for c in hero]),
                recommended=best['action'],selected_action_id=best['id'],raise_to_bb=best.get('raise_to_bb'),
                selected_by='training_deals_only',best_evaluation_action_id=eval_best['id'],
                evaluation_regret_point_bb=max(0.,eval_best['ev_bb']-best['ev_bb']),
                ev_bb=best['ev_bb'],mc_separated=clear,actions=results,seed=seed,
                confidence='MC_SEPARATED_MODEL_UNVALIDATED' if clear else 'LOW_MC_OR_MODEL_CONFIDENCE',
                solver_validated=False,mode='chip_ev_plus_declared_immediate_bounty',
                assumptions=['Fixed declared arrival/response priors, not learned population ranges.',
                             'At most the declared number of preflop raises; future hero call/fold fitted on separate training deals.',
                             'Postflop fixed own-cards/public-board policy, one bet per street; no future board or hidden-card access.',
                             'Exact showdown ranks and contribution-level pots; immediate cash only; no payout ICM/future progressive value.',
                             'Confidence interval covers sampling error, not strategy/model error; not a Nash/HRC certificate.'],
                sources=case.get('sources',[]),seconds=round(time.perf_counter()-started,4))
