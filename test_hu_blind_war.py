"""SB remains OOP in a folded-to tournament; ante and priors stay explicit."""
from dataclasses import replace
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from strategy.batch_jobs import atomic_json
from strategy.blind_war import arrival_settings,extract_reference,game_from_reference
from strategy.ev_evaluator import exact_hu_gap
from strategy.policy_store import CompiledPolicy
from strategy.range_catalog import ComboRange,combo_key
from strategy.reference_validation import verify_reference_hand
from strategy.state_contract import BettingState,GameContext,StrategyError
from strategy.texassolver_backend import solve,native_action
from test_hu_operational import make_test_policy,FLOP

HERE=Path(__file__).parent
REFERENCE=HERE/'docs/software-hu-close32-sb40-20261115/sb40-nvt-reference.json'


class BlindWarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.reference=json.loads(REFERENCE.read_text())

    def test_source_geometry_pot_stacks_and_40bb_conservation(self):
        g=game_from_reference(self.reference)
        self.assertEqual(g['context']['positions'],('SB','BB'))
        self.assertEqual((g['context']['dealt_players'],g['root']['actor'],g['root']['oop']),(9,0,0))
        self.assertEqual((g['root']['pot_bb'],g['root']['stacks']),(5.,(38.,37.)))
        self.assertEqual(g['root']['pot_bb']+sum(g['root']['stacks']),80.)

    def test_original_mixes_are_not_renormalized_or_replaced_by_other_actions(self):
        g=game_from_reference(self.reference);sb,bb=map(ComboRange.from_dict,g['ranges'])
        self.assertEqual(dict(bb.weights)[combo_key('Tc6d')],.582)
        self.assertNotIn(combo_key('AcAd'),dict(bb.weights))  # AA raises, it is not in the call prior
        self.assertNotIn(combo_key('7c2d'),dict(sb.weights))
        self.assertEqual(dict(bb.weights)[combo_key('7c2d')],.5)

    def test_raise_and_limp_cannot_silently_share_the_arrival(self):
        changed=copy.deepcopy(self.reference);changed['geometry']['open_to_bb']=1.
        with self.assertRaisesRegex(StrategyError,'ARRIVAL_GEOMETRY'):game_from_reference(changed)

    def test_extractor_rejects_bad_probabilities_and_inconsistent_money(self):
        r=self.reference
        nodes=[];hands=list(r['ranges']['sb_open']['class_frequencies'])
        for value in r['ranges'].values():
            nodes.append(dict(id=value['node_id'],freq={a:[v[h] for h in hands] for a,v in value['all_action_frequencies'].items()},
                table=value['table'],context=value['context']))
        d=dict(hands=hands,nodes=nodes)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.json';atomic_json(p,d);self.assertEqual(extract_reference(p)['geometry'],r['geometry'])
            bad=copy.deepcopy(d);next(n for n in bad['nodes'] if 'raise' in n['freq'])['freq']['raise'][0]=1.5;atomic_json(p,bad)
            with self.assertRaisesRegex(StrategyError,'FREQUENCIES_INVALID'):extract_reference(p)
            bad=copy.deepcopy(d);next(n for n in bad['nodes'] if 'call' in n['freq'])['table']['potBb']=5;atomic_json(p,bad)
            with self.assertRaisesRegex(StrategyError,'GEOMETRY_NOT_OBSERVED'):extract_reference(p)

    def test_confirmed_sb_history_uses_ante_and_six_actions_to_showdown(self):
        ctx=GameContext(('SB','BB'),dealt_players=9,arrival_id='SYNTHETIC_SB40_BBA1')
        root=BettingState(FLOP,5.,(38.,37.),actor=0,oop=0)
        policy=make_test_policy(root,context=ctx)
        with tempfile.TemporaryDirectory() as tmp:
            result=verify_reference_hand(policy,Path(tmp)/'correct',profile_settings=arrival_settings())
            self.assertEqual(result['event_counts'],dict(action=6,board=2))
            self.assertEqual(result['positions'],['SB','BB'])
            self.assertEqual(result['preflop_witness']['recipe']['forced_pot_bb'],2.5)
            self.assertEqual(result['preflop_witness']['recipe']['open_to_bb'],2.)
            self.assertFalse(result['pppoker_windows_validated'])

    def test_native_effective_short_shove_becomes_a_legal_covering_all_in(self):
        from strategy.action_tree import Action,apply_action,is_legal
        state=BettingState(FLOP+('Ts','2h'),15.,(19.665,8.665),committed=(0.,10.),actor=0,oop=0,
            last_full_raise_bb=10.,raises=1,acted=(False,True),raise_rights=(True,False))
        self.assertFalse(is_legal(state,Action('raise',18.665)))
        action=native_action('RAISE 18665.000000',state,1000)
        self.assertEqual(action,Action('all_in',19.665));self.assertTrue(is_legal(state,action))
        called=apply_action(state,action);called=apply_action(called,Action('call',called.call_cost_bb))
        self.assertEqual(called.terminal,'showdown');self.assertAlmostEqual(called.stacks[0],1.)
        self.assertAlmostEqual(called.pot_bb+sum(called.stacks),state.pot_bb+sum(state.stacks))
        with self.assertRaisesRegex(StrategyError,'NATIVE_ACTION_ILLEGAL'):
            native_action('RAISE 18664.000000',state,1000)

    def test_ordinary_bets_remain_ordinary_and_symmetric_shoves_keep_the_same_size(self):
        from strategy.action_tree import Action
        state=BettingState(FLOP,5.,(38.,37.),actor=0,oop=0)
        self.assertEqual(native_action('BET 1000',state,1000),Action('bet',1.))
        self.assertEqual(native_action('BET 37000',state,1000),Action('all_in',38.))
        symmetric=replace(state,stacks=(37.,37.))
        self.assertEqual(native_action('BET 37000',symmetric,1000),Action('all_in',37.))

    @unittest.skipUnless(os.environ.get('HU_STREAM_TEST_BINARY'),'separately installed native binary required')
    def test_native_asymmetric_effective_stacks_match_independent_river_best_response(self):
        from strategy.action_tree import BetMenu
        context=GameContext(('SB','BB'),arrival_id='TINY_NATIVE_SB40_ASYMMETRIC_CONTROL')
        root=BettingState(FLOP+('Ts','2h'),5.,(38.,37.),actor=0,oop=0)
        ranges=(ComboRange((('As5s',1.),),'tiny-sb'),ComboRange((('AhKd',1.),),'tiny-bb'))
        with tempfile.TemporaryDirectory() as tmp:
            bundle=solve(os.environ['HU_STREAM_TEST_BINARY'],os.environ['HU_STREAM_TEST_RESOURCES'],Path(tmp)/'native',
                context,root,ranges,BetMenu((1/3,),2,True),iterations=501,threads=1,accuracy_pct=.5,dump_rounds=1,memory_mb=512)
        policy=CompiledPolicy(bundle)
        independent=exact_hu_gap(root,ranges,policy.menu,policy.probabilities,actions_fn=policy.actions,max_exact_deals=10)
        self.assertLess(abs(independent['nash_conv_bb']-policy.quality['global_gap_bb']),.001)


if __name__=='__main__':unittest.main()
