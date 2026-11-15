"""Replay a complete hand with stored solver frequencies and synthetic readings.

This validates the Software integration. It does not read/click PPPoker and
does not turn synthetic snapshots into a real played hand or solver certificate.
"""
import argparse
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import time

from hand_journal import HandJournal
from preflop_equity import eval7,parse_card
from strategy.batch_jobs import atomic_json
from strategy.confirmed_history import ConfirmedHistory
from strategy.line_policy import LinePolicy
from strategy.operational_profile import OperationalProfile
from strategy.policy_library import PolicyLibrary,LibraryHistory
from strategy.policy_observer import PolicyObserver
from strategy.policy_store import CompiledPolicy
from strategy.range_catalog import joint_deals
from strategy.state_contract import DecisionState,StrategyError,cards
from strategy.strategy_decision import choose
from strategy.suit_policy import rename_card


SEATS={'hero':'BTN','villain':'BB','small':'SB','s1':'UTG','s2':'UTG+1',
       's3':'UTG+2','s4':'LJ','s5':'HJ','s6':'CO'}
SCOPE='STORED_POLICY_WITH_SYNTHETIC_READINGS_NOT_A_PLAYED_PPPOKER_HAND'


def three_street_line(policy,runout):
    """A declared bet/call line, not a claim every hand should triple barrel."""
    cards(tuple(policy.root.board)+tuple(runout),(5,))
    line=LinePolicy(policy);scenes=[line.state]
    for street in range(3):
        for kind in (('bet','call') if policy.root.oop==0 else ('check','bet','call')):
            choices=[a for a in policy.actions(line.state) if a.kind==kind]
            if not choices:raise StrategyError('REFERENCE_MODEL_HAS_NO_ORDINARY_'+kind.upper())
            line.observe(choices[0])
            if line.state.needs_cards:line.reveal(runout[street])
            scenes.append(line.state)
    if line.state.terminal!='showdown':raise StrategyError('REFERENCE_LINE_DID_NOT_REACH_SHOWDOWN')
    pair=max(joint_deals(line.ranges,line.state.board),key=lambda p:p[1],default=None)
    if pair is None:raise StrategyError('REFERENCE_LINE_HAS_NO_COMPATIBLE_PRIVATE_HANDS')
    return scenes,pair[0],line.trace


def synthetic_reading(state,hero,hand_id,*,payouts=None,positions=None):
    """Scalar lab snapshots. No OCR, pixels or input devices participate."""
    positions=SEATS if positions is None else positions
    stacks={'hero':state.stacks[0],'villain':state.stacks[1],**{k:30. for k in positions if k not in ('hero','villain')}}
    if payouts:
        for seat,value in zip(('hero','villain'),payouts):stacks[seat]+=value
    seats={k:dict(occupied=True,stack_bb=round(v,1),confidence='high') for k,v in stacks.items()}
    for k in seats:
        if k not in ('hero','villain'):seats[k].update(in_hand=False,in_hand_confidence='high')
    ts=dict(positions=dict(positions),seats=seats,pot=dict(pot_bb=0. if payouts else round(state.pot_bb,1),confidence='high'),
        bets=[dict(seat=seat,bet_bb=round(state.committed[i],1),confidence='high')
              for i,seat in enumerate(('hero','villain')) if state.committed[i]>0],bets_complete=True,
        to_call=dict(to_call_bb=round(state.call_cost_bb,1),confidence='high'))
    turn=state.actor==0 and not state.terminal and not state.needs_cards
    names=['FOLD','CALL','RAISE'] if state.call_required_bb else ['FOLD','CHECK','BET']
    buttons=dict(status='EXPERIMENTAL_BUTTON_ROW' if turn else 'NO_BUTTON_ROW',
        buttons=[dict(action=a,box=[20+i*120,630,100,40]) for i,a in enumerate(names)] if turn else [])
    return dict(hand=dict(hand_id=hand_id),hero_cards=list(hero),hero_slots=list(hero),
        observation_source=SCOPE,board=dict(cards=list(state.board)),table_state=ts,
        context=dict(mode='chip_ev',stage='mid')),buttons


def verify_reference_hand(policy,output,*,runout=('Ts','2h'),library=None,profile_settings=None):
    output=Path(output)
    if output.exists():raise StrategyError('REFERENCE_VALIDATION_OUTPUT_MUST_BE_NEW')
    if (policy.context.positions not in (('BTN','BB'),('SB','BB')) or policy.context.dealt_players!=9
            or len(policy.root.board)!=3 or policy.root.oop!=policy.context.oop_player):
        raise StrategyError('REFERENCE_VALIDATION_REQUIRES_NINE_HANDED_BTN_OR_SB_VS_BB_FLOP')
    if policy.context.positions==('BTN','BB'):positions=SEATS
    else:
        positions=dict(hero='SB',villain='BB',**{'s'+str(i+1):p for i,p in enumerate(
            ('UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN'))})
    scenes,hands,posterior_trace=three_street_line(policy,tuple(runout))
    output.mkdir(parents=True)
    with ExitStack() as resources:
        journal=HandJournal(output/'hand-history.sqlite3');resources.callback(journal.close)
        settings=(library.data.get('profile_settings',{}) if library and profile_settings is None else profile_settings or {})
        profile=OperationalProfile(policy.fingerprint,**settings)  # actual preflop witness remains required
        history=(LibraryHistory(library,journal,profile_settings=settings) if library else ConfirmedHistory(policy,profile,journal))
        if library:resources.callback(history.close)
        observer=history.observer if library else PolicyObserver(policy,profile)
        history.preflop_manifest=[dict(source='USER_APPROVED_NVT_REFERENCE',sha256=r.fingerprint) for r in policy.ranges]
        table_id='reference-validation'
        # Coverage-driven fixture: choose a stable hand identity for which the
        # hero's actual mixed selections exercise the three ordinary bets.
        # This is not unbiased play sampling or an EV/performance estimate.
        hero_scenes=[s for s in scenes if s.actor==0 and not s.terminal]
        for seed in range(256):
            hand_id='reference-'+policy.fingerprint[:16]+'-'+str(seed)
            if all(choose(policy,DecisionState(policy.context,s,hands[0],table_id,hand_id))['recommended']=='bet' for s in hero_scenes):
                break
        else:raise StrategyError('REFERENCE_TRIPLE_BARREL_COVERAGE_SEED_NOT_FOUND')
        serial=0;captures=[];decisions=[]

        def observe(result,buttons):
            nonlocal serial
            serial+=1
            outcome=history.observe(result,table_id=table_id,buttons=buttons,
                sample_id='synthetic-'+str(serial),captured_at=time.monotonic())
            captures.append(dict(serial=serial,input=copy.deepcopy(result),buttons=copy.deepcopy(buttons),outcome=outcome))
            return outcome

        # Blinds, observed open and final call conserve the configured starting pot.
        recipe=profile.recipe(policy);baseline,buttons=synthetic_reading(policy.root,hands[0],hand_id,positions=positions)
        baseline['board']['cards']=[];ts=baseline['table_state'];ts['pot']['pot_bb']=recipe['forced_pot_bb']
        posted={s:recipe['posts'].get(p,0.) for s,p in positions.items()}
        ts['bets']=[dict(seat=s,bet_bb=v,confidence='high') for s,v in posted.items() if v]
        for seat in ts['seats']:
            ts['seats'][seat].pop('in_hand',None);ts['seats'][seat].pop('in_hand_confidence',None)
        roles=('hero','villain')
        for i,seat in enumerate(roles):ts['seats'][seat]['stack_bb']=policy.root.stacks[i]+recipe['open_to_bb']-posted[seat]
        observe(baseline,buttons)
        opener=roles[profile.preflop_aggressor]
        opened=copy.deepcopy(baseline);opened['table_state']['seats'][opener]['stack_bb']=policy.root.stacks[profile.preflop_aggressor]
        opened['table_state']['pot']['pot_bb']+=recipe['open_to_bb']-posted[opener]
        opened['table_state']['bets']=[b for b in opened['table_state']['bets'] if b['seat']!=opener]
        opened['table_state']['bets'].append(dict(seat=opener,bet_bb=recipe['open_to_bb'],confidence='high'))
        observe(opened,buttons)

        scores=[eval7([parse_card(c) for c in h+scenes[-1].board]) for h in hands]
        shares=(.5,.5) if scores[0]==scores[1] else (1.,0.) if scores[0]>scores[1] else (0.,1.)
        for expected in scenes:
            payouts=tuple(expected.pot_bb*x for x in shares) if expected.terminal else None
            for _ in range(profile.confirmations):
                result,buttons=synthetic_reading(expected,hands[0],hand_id,payouts=payouts,positions=positions)
                outcome=observe(result,buttons)
            if outcome['status']!='CONFIRMED':raise StrategyError('REFERENCE_HISTORY_NOT_CONFIRMED:'+str(outcome))
            actual=history.current(table_id)['state']
            if actual.key()!=expected.key():raise StrategyError('REFERENCE_CONFIRMED_STATE_DIFFERS_FROM_SOLVER_STATE')
            if expected.actor==0 and not expected.terminal:
                advice=observer.advise(table_key=table_id,hand_key=hand_id,table_state=result['table_state'],
                    hero_cards=hands[0],board=expected.board,mode=policy.context.mode,stage=policy.context.stage)
                if advice['status']!='ADVICE' or advice['policy_sha256']!=policy.fingerprint:
                    raise StrategyError('REFERENCE_BOT_LOOKUP_FAILED:'+str(advice))
                if advice['recommended']!='bet':raise StrategyError('REFERENCE_SELECTED_ACTION_DIFFERS_FROM_EXECUTED_LAB_ACTION')
                _,row=policy.row(expected,hands[0]);actions=policy.actions(expected)
                got={a['action_id']:a for a in advice['candidates']}
                if set(got)!={a.id for a in actions}:raise StrategyError('REFERENCE_ACTION_MENU_CHANGED')
                for action in actions:
                    if (got[action.id]['frequency']!=row['frequencies'][action.id]
                            or got[action.id]['additional_bb']!=action.amount_bb):
                        raise StrategyError('REFERENCE_FREQUENCY_OR_SIZE_CHANGED')
                decisions.append(advice)
        hand=journal.export_hand(table_id,hand_id)
        counts={kind:sum(e['payload'].get('event_type')==kind for e in hand['events']) for kind in ('action','board')}
        expected_actions=6 if policy.root.oop==0 else 9
        if not hand['chain_valid'] or counts!={'action':expected_actions,'board':2}:
            raise StrategyError('REFERENCE_HAND_ACTIONS_OR_REVEALS_DO_NOT_MATCH_POSITIONAL_LINE')
        if {d['street'] for d in decisions}!={'FLOP','TURN','RIVER'}:
            raise StrategyError('REFERENCE_DECISIONS_NOT_CONFIRMED_ON_THREE_STREETS')
        summary=dict(status='PASS',scope=SCOPE,policy_sha256=policy.fingerprint,quality=policy.quality,
            positions=list(policy.context.positions),operational_profile_settings=settings,
            complete_to_showdown=True,event_counts=counts,decisions=len(decisions),
            private_hands_known_in_lab=[list(h) for h in hands],board=list(scenes[-1].board),
            preflop_witness=history.current(table_id)['witness'],journal_chain_valid=True,
            frequencies_and_sizes_exactly_match_stored_policy=True,
            hero_selected_actions_match_lab_actions=True,coverage_seed=seed,
            scenario_sampling='COVERAGE_DRIVEN_TRIPLE_BARREL_NOT_UNBIASED_PLAY_OR_EV_ESTIMATION',
            opponent_actions='SCRIPTED_CHECK_CALL_WITH_POSITIVE_POSTERIOR_SUPPORT',
            library_routing_tested=library is not None,pppoker_windows_validated=False,input_devices_used=False)
        atomic_json(output/'result.json',summary);atomic_json(output/'hand.json',hand)
        atomic_json(output/'decisions.json',decisions);atomic_json(output/'synthetic-captures.json',captures)
        atomic_json(output/'posterior-trace.json',posterior_trace)
        return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--policy');group.add_argument('--library');p.add_argument('--output',required=True)
    p.add_argument('--turn');p.add_argument('--river');p.add_argument('--flop',nargs=3)
    args=p.parse_args(argv)
    if args.flop and not args.library:p.error('--flop requires a policy library')
    library=PolicyLibrary(args.library) if args.library else None
    policy=library.open(args.flop or next(iter(library.entries))) if library else CompiledPolicy.load(args.policy)
    mapping=getattr(policy,'mapping',dict(zip('cdhs','cdhs')))
    runout=(args.turn or rename_card('Ts',mapping),args.river or rename_card('2h',mapping))
    try:summary=verify_reference_hand(policy,args.output,runout=runout,library=library)
    finally:
        if hasattr(policy,'close'):policy.close()
    print(json.dumps(dict(status=summary['status'],policy_sha256=summary['policy_sha256'],
        scope=summary['scope'],output=str(Path(args.output).resolve())),indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
