"""Check a transferred full policy and exact suit routing without gameplay input."""
import argparse
import itertools
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_jobs import atomic_json
from strategy.policy_library import PolicyLibrary
from strategy.river_validation import review_reference_river
from strategy.state_contract import BettingState,DecisionState,StrategyError
from strategy.strategy_decision import choose
from strategy.suit_policy import SUITS,exact_suit_map,rename_card,rename_state


def verify_suit_queries(library,source,proof):
    alias=None
    try:
        for permutation in itertools.permutations(SUITS):
            mapping=dict(zip(SUITS,permutation));board=[rename_card(c,mapping) for c in source.root.board]
            if set(board)!=set(source.root.board):break
        mapping=exact_suit_map(source.root.board,board,source.ranges)
        alias=library.open(board)
        if alias.quality.get('source_policy_sha256')!=source.fingerprint:raise StrategyError('BATCH_ALIAS_SOURCE_CHANGED')
        probes={}
        for street,p in proof['lookup_validation']['probes'].items():
            state=BettingState.from_dict(source.get_node(p['node_id'])['state'])
            observed=rename_state(state,mapping);hand=tuple(rename_card(c,mapping) for c in p['hero_cards'])
            probabilities=source.probabilities(state,tuple(p['hero_cards']))
            if alias.probabilities(observed,hand)!=probabilities or alias.actions(observed)!=source.actions(state):
                raise StrategyError('BATCH_ALIAS_CHANGED_FREQUENCIES_OR_SIZES')
            advice=choose(alias,DecisionState(alias.context,observed,hand,'download-validation','alias-'+street))
            if advice['status']!='ADVICE':raise StrategyError('BATCH_ALIAS_QUERY_FAILED')
            if [c['frequency'] for c in advice['candidates']]!=probabilities:
                raise StrategyError('BATCH_ALIAS_DECISOR_CHANGED_FREQUENCIES')
            probes[street]=dict(node_id=advice['node_id'],hero_cards=list(hand),
                actions=advice['candidates'],query_status=advice['status'])
        if set(probes)!={'flop','turn','river'}:raise StrategyError('BATCH_ALIAS_THREE_STREETS_REQUIRED')
        return dict(board=board,derived_policy_sha256=alias.fingerprint,mapping=mapping,probes=probes,new_solve=False)
    finally:
        if alias is not None:alias.close()


def verify_delivery(receipt_path,output,*,ordinal,require_windows=False):
    if require_windows and platform.system()!='Windows':raise StrategyError('NATIVE_WINDOWS_REQUIRED')
    if Path(output).exists():raise StrategyError('BATCH_VALIDATION_OUTPUT_MUST_BE_NEW')
    receipt=json.loads(Path(receipt_path).read_text())
    if (receipt.get('status')!='PASS' or receipt.get('new_flops')!=1 or receipt.get('total_models')!=1
            or receipt.get('pilot_included') or receipt['policies'][0]['ordinal']!=ordinal):
        raise StrategyError('BATCH_VALIDATION_REQUIRES_THE_REQUESTED_SINGLE_TRANSFERRED_MODEL')
    proof=receipt['policies'][0];library=PolicyLibrary(receipt['library']);source=library.open(proof['board'])
    try:
        if source.fingerprint!=proof['policy_sha256']:raise StrategyError('BATCH_VALIDATION_POLICY_CHANGED')
        alias_proof=verify_suit_queries(library,source,proof)
        from strategy.range_catalog import DECK
        runout=[]
        for card in ('Ts','2h')+DECK:
            if card not in source.root.board and card not in runout:runout.append(card)
            if len(runout)==2:break
        river=review_reference_river(source,tuple(runout))
        result=dict(status='PASS',ordinal=ordinal,board=proof['board'],platform=platform.platform(),
            policy_sha256=source.fingerprint,file_sha256=proof['file_sha256'],
            archive_sha256=proof['archive']['sha256'],native_target_met=source.quality.get('converged'),
            global_native_gap_bb=source.quality.get('global_gap_bb'),coverage=dict(
                public_nodes=source.node_count,nodes_by_street=source.quality['nodes_by_street'],
                structurally_complete=source.quality['structurally_complete']),
            source_lookup=proof['lookup_validation'],exact_suit_alias=alias_proof,
            independent_river=dict(scope=river['scope'],runout=runout,joint_private_deals=river['joint_private_deals'],
                nash_conv_bb=river['nash_conv_bb'],exact_enumeration=river['exact_enumeration']),
            scope='TRANSFERRED_FULL_POLICY_THREE_STREET_QUERY_EXACT_SUIT_ROUTING_AND_CONDITIONAL_RIVER',
            input_devices_used=False,pppoker_windows_validated=False,user_notebook_validated=False)
        atomic_json(output,result);return result
    finally:
        source.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipt',required=True)
    p.add_argument('--output',required=True);p.add_argument('--ordinal',required=True,type=int)
    p.add_argument('--require-windows',action='store_true');args=p.parse_args(argv)
    r=verify_delivery(args.receipt,args.output,ordinal=args.ordinal,require_windows=args.require_windows)
    print(json.dumps({k:r[k] for k in ('status','ordinal','board','platform','policy_sha256','native_target_met')}));return 0


if __name__=='__main__':raise SystemExit(main())
