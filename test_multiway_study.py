"""Rule/arrival diagnostics for the THREE-player lab, not solver certification."""
from dataclasses import replace
import json
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest

from strategy.multiway_state import MultiwayState, POSITIONS, act, action_menu, reveal, settle
from strategy.multiway_study import (ThreePlayerSampler, checkdown_equity,
    extract_candidates, make_plan, replay_cases)
from strategy.range_catalog import ComboRange, DECK
from strategy.state_contract import StrategyError, GameContext
from tools.prepare_multiway_pilot import main as prepare

ROOT = Path(__file__).resolve().parent
REFS = ROOT / 'docs/multiway-mp-btn-bb40-20261116/referencias-nvt.json'


class MultiwayRulesTests(unittest.TestCase):
    def root(self):
        return MultiwayState(('As', '7d', '2c'))

    def test_geometry_and_bb_first_not_mp_or_btn(self):
        s = self.root()
        self.assertEqual(s.pot_bb, 7.5)
        self.assertEqual(s.actor, 2)
        self.assertEqual(s.stacks, (38., 38., 37.))
        self.assertEqual([POSITIONS[act(s, 'check').actor]], ['MP'])
        self.assertEqual(act(act(s, 'check'), 'check').actor, 1)

    def test_cbet_call_checkraise_all_players_must_respond(self):
        s = act(act(self.root(), 'check'), 'bet', 2.5)
        self.assertEqual(s.pending, (1, 2))
        s = act(act(s, 'call'), 'raise', 10.)
        self.assertEqual(s.pending, (0, 1))
        self.assertEqual(s.call_required_bb, 7.5)
        s = act(act(s, 'call'), 'fold')
        self.assertEqual(s.phase, 'deal')
        self.assertEqual(s.pot_bb, 30.)
        s = reveal(s, '8h')
        self.assertEqual(s.pending, (2, 0))
        self.assertEqual(s.folded, (False, True, False))
        self.assertEqual(s.committed, (0., 0., 0.))

    def test_checkraise_right_after_check(self):
        s = act(act(self.root(), 'check'), 'check')
        s = act(act(s, 'bet', 2.5), 'call')
        self.assertTrue(s.can_raise)
        self.assertEqual(act(s, 'raise', 10.).pending, (1, 2))

    def test_short_all_in_does_not_reopen_prior_bettor(self):
        s = replace(self.root(), stacks=(38., 3., 37.))
        s = act(act(s, 'check'), 'bet', 2.)
        s = act(s, 'raise', 3.)  # BTN all-in, less than a full 2 BB raise
        s = act(s, 'call')      # BB still has a call/raise decision
        self.assertEqual(s.actor, 0)
        self.assertFalse(s.can_raise)
        with self.assertRaisesRegex(StrategyError, 'RAISE_NOT_REOPENED'):
            act(s, 'raise', 5.)
        self.assertEqual(act(s, 'call').phase, 'deal')

    def test_multiple_short_all_ins_can_reopen_cumulatively(self):
        s = replace(self.root(), stacks=(38., 3., 4.))
        s = act(act(s, 'check'), 'bet', 2.)
        s = act(act(s, 'raise', 3.), 'raise', 4.)
        self.assertEqual(s.actor, 0)
        # Rights reopen numerically, but both opponents are all-in: only call/fold.
        self.assertEqual(max(s.committed) - s.acted_to[0], s.last_full_raise_bb)
        self.assertFalse(s.can_raise)
        self.assertEqual([a['kind'] for a in action_menu(s)], ['fold', 'call'])

    def test_under_minimum_raise_requires_all_in(self):
        s = act(act(self.root(), 'check'), 'bet', 2.)
        with self.assertRaisesRegex(StrategyError, 'UNDER_MINIMUM'):
            act(s, 'raise', 3.)

    def test_cannot_check_call_or_deal_out_of_order(self):
        with self.assertRaises(StrategyError):
            act(self.root(), 'call')
        with self.assertRaises(StrategyError):
            act(self.root(), 'fold')
        with self.assertRaises(StrategyError):
            reveal(self.root(), '8h')
        s = act(self.root(), 'bet', 2.)
        with self.assertRaises(StrategyError):
            act(s, 'check')

    def test_pot_raise_calls_before_calculating_fraction(self):
        s = act(self.root(), 'bet', 2.5)
        sizes = action_menu(s)
        # current pot10, call2.5, pot raise TO2.5+(10+2.5)=15
        self.assertIn(15., [a.get('to_bb') for a in sizes])
        self.assertEqual([a['kind'] for a in sizes[:2]], ['fold', 'call'])

    def test_ante_is_dead_money_not_live_side_pot_contribution(self):
        s = act(act(act(self.root(), 'bet', 37.), 'raise', 38.), 'call')
        s = reveal(reveal(s, '8h'), 'Qc')
        r = settle(s, (('Ah', 'Kd'), ('Ks', 'Qd'), ('7s', '7c')))
        self.assertEqual([p['amount_bb'] for p in r['layers']], [118.5, 2.])
        self.assertEqual(r['payouts_bb'], [2., 0., 118.5])
        self.assertAlmostEqual(sum(r['final_stacks_bb']), 120.5)
        self.assertFalse(r['bounty_utility_calculated'])

    def test_uncalled_excess_returned_and_folded_player_never_wins(self):
        s = act(self.root(), 'bet', 37.)
        s = act(act(s, 'fold'), 'fold')
        r = settle(s)
        self.assertEqual(r['payouts_bb'], [0., 0., 44.5])
        self.assertTrue(r['layers'][-1]['uncalled_return'])
        self.assertAlmostEqual(sum(r['final_stacks_bb']), 120.5)

    def test_split_showdown_uses_all_winners_not_tie_over_two(self):
        s = MultiwayState(('As', 'Ks', 'Qs', 'Js', 'Ts'), phase='showdown', pending=())
        r = settle(s, (('2h', '3d'), ('4h', '5d'), ('6h', '7c')))
        self.assertEqual(r['payouts_bb'], [2.5, 2.5, 2.5])

    def test_duplicate_cards_and_unfinished_history_rejected(self):
        with self.assertRaises(StrategyError):
            MultiwayState(('As', 'As', '2c'))
        with self.assertRaises(StrategyError):
            settle(self.root())
        s = MultiwayState(('As', 'Ks', 'Qs', 'Js', 'Ts'), phase='showdown', pending=())
        with self.assertRaisesRegex(StrategyError, 'COLLISION'):
            settle(s, (('2h', '3d'), ('2h', '5d'), ('6h', '7c')))

    def test_synthetic_replays_have_three_streets_and_no_policy_claim(self):
        for case in replay_cases():
            self.assertFalse(case['optimality_claimed'])
            self.assertIsNone(case['action_frequencies'])
            self.assertAlmostEqual(sum(case['showdown']['final_stacks_bb']), 120.5)
            streets = {len(e[side]['board']) for e in case['history'] for side in ('before', 'after')}
            self.assertEqual(streets, {3, 4, 5})

    def test_random_legal_hands_conserve_chips_and_preserve_player_ids(self):
        rng = random.Random(20261116)
        hands = (('Ah', 'Kd'), ('Ks', 'Qd'), ('7s', '7c'))
        for _ in range(300):
            s = self.root()
            dead = set(s.board + tuple(c for h in hands for c in h))
            for step in range(600):
                if s.phase in ('fold', 'showdown'):
                    r = settle(s, hands)
                    self.assertAlmostEqual(sum(r['payouts_bb']), s.pot_bb)
                    self.assertAlmostEqual(sum(r['final_stacks_bb']), 120.5)
                    self.assertTrue(all(p >= -1e-7 for p in r['final_stacks_bb']))
                    break
                if s.phase == 'deal':
                    c = rng.choice([c for c in DECK if c not in dead])
                    dead.add(c)
                    s = reveal(s, c)
                else:
                    a = rng.choice(action_menu(s))
                    s = act(s, a['kind'], a.get('to_bb'))
                self.assertAlmostEqual(sum(s.stacks) + s.pot_bb, 120.5)
            else:
                self.fail('Random legal hand failed to terminate')


class StudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs = json.loads(REFS.read_text(encoding='utf-8'))

    def test_source_vectors_and_missing_overcall_are_explicit(self):
        for ref in self.refs.values():
            self.assertEqual([r['role'] for r in ref['ranges']], list(POSITIONS))
            for r in ref['ranges']:
                self.assertEqual(len(r['class_frequencies']), 169)
                self.assertFalse(r['exact_hrc_parent_confirmed'])
                self.assertAlmostEqual(ComboRange.from_dict(r['combo_range']).mass, r['combo_mass'])
            self.assertIn('NOT_BB_OVERCALL', ref['ranges'][2]['arrival_status'])

    def synthetic_pack(self):
        ref = self.refs['chip_ev']
        hands = list(ref['ranges'][0]['class_frequencies'])
        nodes = []
        for row in ref['ranges']:
            freq = [row['class_frequencies'][h] for h in hands]
            nodes.append(dict(id=row['node_id'], context=row['source_context'],
                table=row['source_table'], freq={row['selected_action']:freq,
                'fold':[1-v for v in freq]}, source='SYNTHETIC_EXTRACTOR_FIXTURE'))
        return dict(hands=hands, nodes=nodes)

    def test_extractor_preserves_exact_selected_vectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic-reference.json'
            path.write_text(json.dumps(self.synthetic_pack()), encoding='utf-8')
            got = extract_candidates(path, 'chip_ev', 'mid')
            for actual, expected in zip(got['ranges'], self.refs['chip_ev']['ranges']):
                self.assertEqual(actual['class_frequencies'], expected['class_frequencies'])
                self.assertEqual(actual['combo_mass'], expected['combo_mass'])
            self.assertIn('NOT_BB_OVERCALL', got['ranges'][2]['arrival_status'])

    def test_extractor_rejects_context_and_probability_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic-invalid.json'
            pack = self.synthetic_pack()
            pack['nodes'][0]['context'] = dict(pack['nodes'][0]['context'], stack=80)
            path.write_text(json.dumps(pack), encoding='utf-8')
            with self.assertRaisesRegex(StrategyError, 'CONTEXT_DISAGREE'):
                extract_candidates(path, 'chip_ev', 'mid')
            pack = self.synthetic_pack()
            pack['nodes'][0]['freq']['raise'][0] = 2.
            path.write_text(json.dumps(pack), encoding='utf-8')
            with self.assertRaisesRegex(StrategyError, 'FREQUENCIES_INVALID'):
                extract_candidates(path, 'chip_ev', 'mid')

    def test_plan_does_not_turn_reference_ranges_into_completed_policies(self):
        plan = make_plan(self.refs['chip_ev'], self.refs['pko'])
        self.assertEqual(plan['solved_flops'], 0)
        self.assertEqual(plan['executable_policies'], 0)
        self.assertEqual(plan['root']['stacks'], (38., 38., 37.))
        self.assertFalse(plan['menu']['forced_checkdown'])
        self.assertIsNone(plan['pko_economy']['bounties'])
        self.assertEqual(plan['mp_source_position'], 'LJ')

    def test_joint_sampler_rejects_whole_triples_not_last_player(self):
        r = lambda values, name: ComboRange(tuple(values), name)
        # Three compatible deals have weights1,2,2; sequential resampling biases them.
        ranges = (r((('AhAd', 1.), ('KhKd', 2.)), 'mp'),
                  r((('AhQd', 1.), ('JhJd', 1.)), 'btn'),
                  r((('9h9d', 1.),), 'bb'))
        sampler = ThreePlayerSampler(ranges, ('2c', '3c', '4c'))
        rng, counts = random.Random(17), {}
        for _ in range(12000):
            hands, runout = sampler.sample(rng)
            key = tuple(''.join(h) for h in hands)
            counts[key] = counts.get(key, 0) + 1
            self.assertEqual(len(set(sum(hands, ()) + runout + sampler.board)), 11)
        self.assertEqual(len(counts), 3)
        observed = sorted(v / 12000 for v in counts.values())
        for actual, expected in zip(observed, (.2, .4, .4)):
            self.assertLess(abs(actual - expected), .025)

    def test_impossible_joint_distribution_is_rejected(self):
        r = ComboRange((('AhAd', 1.),), 'same-cards')
        with self.assertRaisesRegex(StrategyError, 'NO_COMPATIBLE'):
            ThreePlayerSampler((r, r, r), ('2c', '3c', '4c'))

    def test_checkdown_diagnostic_is_reproducible_and_not_action_ev(self):
        a = checkdown_equity(self.refs['chip_ev'], ('As', '7d', '2c'), 200, 9)
        b = checkdown_equity(self.refs['chip_ev'], ('As', '7d', '2c'), 200, 9)
        self.assertEqual(a, b)
        self.assertAlmostEqual(sum(r['showdown_share'] for r in a['roles']), 1.)
        self.assertFalse(a['optimal_actions_calculated'])
        self.assertFalse(a['pkobounty_utility_calculated'])

    def test_existing_hu_contract_remains_explicitly_hu(self):
        with self.assertRaises(StrategyError):
            GameContext(('MP', 'BTN', 'BB'), arrival_id='not-a-hu-game')

    def test_preparation_never_overwrites_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'new'
            self.assertEqual(prepare(['--output', str(out), '--samples', '100']), 0)
            original = (out / 'plano.json').read_bytes()
            with self.assertRaises(SystemExit):
                prepare(['--output', str(out), '--samples', '100'])
            self.assertEqual((out / 'plano.json').read_bytes(), original)

    @unittest.skipUnless(shutil.which('node'), 'Node is only needed to test the HRC script API contract')
    def test_hrc_script_with_documented_api_and_java_like_arrays(self):
        script = ROOT / 'hrc/MP_BTN_BB40_MENU.js'
        code = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const scope = {}; vm.createContext(scope); vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), scope);
function ctx(bets) { return {getBetCount:()=>bets, sizingAllIn:()=>3800,
 sizingBigBlinds:(n)=>n*100, sizingPot:(n)=>Math.round(n*750),
 sizingsPreflop:()=>({0:800,length:1})}; }
assert.equal(scope.getSizingsPreflop(ctx(1))[0], 200);
assert.equal(scope.getSizingsPreflop(ctx(2))[0], 800);
assert.equal(scope.getSizingsPreflop(ctx(3))[0], 800);
assert.equal(scope.getSizingsPostflop(ctx(0)).length, 5);
assert.equal(scope.getSizingsPostflop(ctx(1)).length, 2);
assert.equal(scope.getSizingsPostflop(ctx(2)).length, 2);
assert.equal(scope.getSizingsPostflop(ctx(3)).length, 0);
assert.equal(scope.canFlatCallPreflop(ctx(2)), true);
assert.equal(scope.canFlatCallPostflop(ctx(2)), true);
assert.equal(scope.hasNextStreetBetting(ctx(2)), true);
console.log('HRC_SCRIPT_CONTRACT_ONLY_PASS_NOT_HRC_NATIVE_EXECUTION');
'''
        result = subprocess.run(['node', '-e', code, str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
