"""Independent exact river EV/BR validation; never overwrites the mixed policy.

Matrices enumerate private blockers. A best response maximizes only AFTER
summing the opponent belief, so the actor cannot see the opponent's cards.
This conditional river calculation does not certify the full flop game.
"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import time

import numpy as np

from preflop_equity import eval7,parse_card
from strategy.action_tree import apply_action
from strategy.batch_jobs import atomic_json
from strategy.line_policy import LinePolicy
from strategy.policy_library import PolicyLibrary
from strategy.policy_store import CompiledPolicy
from strategy.range_catalog import DECK,combo_cards
from strategy.state_contract import StrategyError


def exact_river_review(root,ranges,probability,actions_fn,*,max_grid=2000000,max_nodes=128):
    started=time.monotonic()
    if len(root.board)!=5 or root.needs_cards or root.terminal:raise StrategyError('EXACT_RIVER_DECISION_ROOT_REQUIRED')
    priors=tuple(r.without(root.board) for r in ranges)
    keys=[tuple(k for k,w in r.weights) for r in priors]
    if len(keys[0])*len(keys[1])>max_grid:raise StrategyError('EXACT_RIVER_GRID_BUDGET_EXHAUSTED_NO_PARTIAL_EV')
    weights=[np.array([w for k,w in r.weights],dtype=np.float64) for r in priors]
    index={c:i for i,c in enumerate(DECK)}
    masks=[np.array([sum(1<<index[c] for c in combo_cards(k)) for k in own],dtype=np.uint64) for own in keys]
    compatible=(masks[0][:,None]&masks[1][None,:])==0
    joint=weights[0][:,None]*weights[1][None,:]*compatible
    total=float(joint.sum())
    if total<=0:raise StrategyError('NO_COMPATIBLE_JOINT_DEAL')
    scores=[[eval7([parse_card(c) for c in combo_cards(k)+root.board]) for k in own] for own in keys]
    rank={s:i for i,s in enumerate(sorted(set(scores[0]+scores[1])))}
    ranks=[np.array([rank[s] for s in values]) for values in scores]
    shares=(ranks[0][:,None]>ranks[1][None,:]).astype(np.float64)+.5*(ranks[0][:,None]==ranks[1][None,:])
    shape=compatible.shape;nodes={}

    def node(state):
        if state not in nodes:
            if len(nodes)>=max_nodes:raise StrategyError('EXACT_RIVER_NODE_BUDGET_EXHAUSTED_NO_PARTIAL_EV')
            if state.needs_cards:raise StrategyError('EXACT_RIVER_UNEXPECTED_CHANCE')
            actions=tuple(actions_fn(state))
            p=np.array([probability(state,combo_cards(k)) for k in keys[state.actor]],dtype=np.float64)
            if (p.shape!=(len(keys[state.actor]),len(actions)) or not len(actions)
                    or not np.isfinite(p).all() or (p<0).any() or not np.allclose(p.sum(axis=1),1,rtol=0,atol=1e-6)):
                raise StrategyError('EXACT_RIVER_INVALID_BEHAVIORAL_POLICY')
            children=tuple(apply_action(state,a) for a in actions)
            nodes[state]=(actions,p,children)
        return nodes[state]

    @lru_cache(maxsize=4)
    def utility(state):
        if not state.terminal:raise StrategyError('EXACT_RIVER_NONTERMINAL_PAYOFF')
        share=shares if state.terminal=='showdown' else float(state.winner==0)
        return share*state.pot_bb-(root.stacks[0]-state.stacks[0])-root.pot_bb/2

    @lru_cache(maxsize=4)
    def profile(state):
        if state.terminal:return utility(state)
        actions,p,children=node(state);value=np.zeros(shape,dtype=np.float64)
        for i,child in enumerate(children):
            own=p[:,i,None] if state.actor==0 else p[None,:,i]
            value+=own*profile(child)
        return value

    def response(player,state,opponent_reach):
        if state.terminal:
            values=utility(state)*compatible
            return (values@(weights[1]*opponent_reach) if player==0
                    else -values.T@(weights[0]*opponent_reach))
        actions,p,children=node(state)
        if state.actor==player:
            return np.maximum.reduce([response(player,c,opponent_reach) for c in children])
        return sum((response(player,c,opponent_reach*p[:,i]) for i,c in enumerate(children)),
                   np.zeros(len(keys[player]),dtype=np.float64))

    ev=float(np.sum(profile(root)*joint)/total)
    br=[float(np.dot(weights[player],response(player,root,np.ones(len(keys[1-player]))))/total) for player in (0,1)]
    if br[0]<ev-1e-7 or br[1]<-ev-1e-7:raise StrategyError('EXACT_RIVER_BEST_RESPONSE_BELOW_PROFILE_EV')
    actor=root.actor;actions,p,children=node(root);rows={}
    denominator=compatible@weights[1] if actor==0 else compatible.T@weights[0]
    values=[]
    for child in children:
        matrix=profile(child)*compatible
        numerator=matrix@weights[1] if actor==0 else -matrix.T@weights[0]
        values.append(np.divide(numerator,denominator,out=np.zeros_like(numerator),where=denominator>0)+root.pot_bb/2)
    for i,key in enumerate(keys[actor]):
        if denominator[i]<=0:continue
        evs={a.id:float(v[i]) for a,v in zip(actions,values)};best=max(evs.values())
        rows[key]=dict(frequencies={a.id:float(p[i,j]) for j,a in enumerate(actions)},
            action_ev_bb_from_current_node=evs,
            frozen_profile_ev_bb_from_current_node=sum(p[i,j]*evs[a.id] for j,a in enumerate(actions)),
            local_best_action_ids=[k for k,v in evs.items() if best-v<1e-9])
    return dict(method='exact_river_frozen_profile_evs_and_information_set_best_responses',
        scope='CONDITIONAL_RIVER_PRIORS_AND_DECLARED_MENU_NOT_FULL_FLOP_GTO_CERTIFICATION',
        root=root.to_dict(),range_sha256=[r.fingerprint for r in priors],
        joint_private_deals=int(compatible.sum()),public_decision_nodes=len(nodes),
        frozen_profile_centered_ev_player0_bb=ev,best_response_centered_bb=br,
        nash_conv_bb=max(0.,sum(br)),exploitability_bb=max(0.,sum(br)/2),
        local_action_ev_scope='ONE_ACTION_DEVIATION_THEN_BOTH_PLAYERS_FOLLOW_FROZEN_POLICY',
        root_actor=actor,actions=[a.to_dict() for a in actions],combos=rows,
        exact_enumeration=True,monte_carlo_used=False,policy_modified=False,
        elapsed_seconds=time.monotonic()-started,pppoker_windows_validated=False)


def review_reference_river(policy,runout=('Ts','2h')):
    if len(policy.root.board)!=3:raise StrategyError('REFERENCE_RIVER_REVIEW_REQUIRES_FLOP_POLICY')
    line=LinePolicy(policy)
    for card in runout:
        for kind in ('check','bet','call'):
            action=next((a for a in policy.actions(line.state) if a.kind==kind),None)
            if action is None:raise StrategyError('REFERENCE_RIVER_LINE_OUTSIDE_DECLARED_TREE')
            line.observe(action)
        line.reveal(card)
    action=next(a for a in policy.actions(line.state) if a.kind=='check');line.observe(action)
    result=exact_river_review(line.state,line.ranges,policy.probabilities,policy.actions)
    result.update(source_policy_sha256=policy.fingerprint,source_native_global_gap_bb=policy.quality.get('global_gap_bb'),
        source_native_gap_has_different_scope=True,observed_path=line.trace)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--policy');g.add_argument('--library');p.add_argument('--output',required=True)
    args=p.parse_args(argv)
    if Path(args.output).exists():p.error('Output already exists; choose a new path')
    library=PolicyLibrary(args.library) if args.library else None
    policy=library.open(next(iter(library.entries))) if library else CompiledPolicy.load(args.policy)
    try:result=review_reference_river(policy)
    finally:
        if hasattr(policy,'close'):policy.close()
    atomic_json(args.output,result)
    print(json.dumps({k:result[k] for k in ('method','scope','joint_private_deals','nash_conv_bb','source_policy_sha256','elapsed_seconds')},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
