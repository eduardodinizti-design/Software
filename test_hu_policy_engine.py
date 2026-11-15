"""Economic, information-set and integration counterexamples for the HU engine."""
from dataclasses import asdict, replace
import copy
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

from strategy.action_tree import Action, BetMenu, apply_action, is_legal, legal_actions
from strategy.board_features import compare_distributions
from strategy.ev_evaluator import (CFRTrainer, attach_evaluation, evaluate_profile,
                                   exact_river_gap, exact_hu_gap, terminal_utility)
from strategy.line_policy import LinePolicy
from strategy.policy_observer import PolicyObserver
from strategy.policy_store import CompiledPolicy, save_policy
from strategy.range_catalog import ComboRange, DealSampler, combo_key, joint_deals
from strategy.state_contract import (BettingState, DecisionState, GameContext,
                                     StrategyError, reveal)
from strategy.strategy_decision import choose
from strategy.texassolver_backend import input_commands, native_action, native_range


RIVER = ('Kc', '8s', '3d', 'Ts', '2h')


def ip_state(board=RIVER, pot=25, stacks=(50, 50)):
    return BettingState(board, pot, stacks, oop=1, acted=(False, True), history=('1:check:0',))


def context():
    return GameContext(('BTN', 'BB'), arrival_id='synthetic-test-arrival')


def river_ranges():
    return (ComboRange((('As5s', 1), ('6c5c', 1), ('AhKd', 1)), 'synthetic-hero'),
            ComboRange((('QsJs', 1), ('KhQd', 1)), 'synthetic-villain'))


def trained_river(iterations=3000):
    return CFRTrainer(context(), ip_state(), river_ranges(), BetMenu((2 / 3,), 0, False), seed=217).train(iterations)


class StateAndRangeTests(unittest.TestCase):
    def test_ip_turn_requires_an_observed_check(self):
        with self.assertRaisesRegex(StrategyError, 'CONFIRMED_OOP_CHECK'):
            BettingState(RIVER, 25, (50, 50), oop=1)

    def test_positions_are_part_of_the_game_and_postflop_order(self):
        ctx = GameContext(('SB', 'BB'), arrival_id='sb-open')
        self.assertEqual(ctx.oop_player, 0)
        with self.assertRaisesRegex(StrategyError, 'ORDER_MISMATCH'):
            CFRTrainer(ctx, ip_state(), river_ranges())

    def test_heads_up_button_small_blind_is_ip(self):
        self.assertEqual(GameContext(('SB', 'BB'), dealt_players=2, arrival_id='hu').oop_player, 1)

    def test_pko_icm_are_not_silently_chip_ev(self):
        for kw in ({'mode': 'icm'}, {'tournament_format': 'pko'}):
            with self.subTest(kw=kw), self.assertRaisesRegex(StrategyError, 'NOT_PKO_OR_ICM'):
                GameContext(('BTN', 'BB'), arrival_id='test', **kw)

    def test_nonfinite_or_negative_money_rejected(self):
        for value in (math.nan, math.inf, -1, True, '25'):
            with self.subTest(value=value), self.assertRaises(StrategyError):
                ip_state(pot=value)

    def test_hero_board_collision_is_not_a_strategy(self):
        with self.assertRaisesRegex(StrategyError, 'HERO_BOARD_COLLISION'):
            DecisionState(context(), ip_state(), ('Kc', 'As'), 't', 'h')

    def test_169_classes_expand_without_dividing_weights(self):
        r = ComboRange.from_classes({'AA': .5, 'AKs': .25, 'AKo': .1}, 'source')
        self.assertEqual(len(r.weights), 22)
        self.assertAlmostEqual(r.mass, 6 * .5 + 4 * .25 + 12 * .1)
        self.assertAlmostEqual(dict(r.weights)[combo_key('AsAh')], .5)

    def test_blockers_remove_whole_combos_and_renormalize(self):
        r = ComboRange.from_classes({'A5s': .3}, 'source').without(('As',))
        self.assertEqual(len(r.weights), 3)
        self.assertAlmostEqual(r.mass, .9)
        self.assertAlmostEqual(sum(r.probabilities().values()), 1)

    def test_weighted_bayes_retains_slowplays_and_requires_a_model(self):
        r = ComboRange((('AsAh', 1), ('KsKh', 1)), 'prior')
        p = r.posterior({combo_key('AsAh'): .2, combo_key('KsKh'): .8}, 'check')
        self.assertAlmostEqual(p.probabilities()[combo_key('AsAh')], .2)
        self.assertNotEqual(r.fingerprint, p.fingerprint)
        with self.assertRaisesRegex(StrategyError, 'MISSING_ACTION'):
            r.posterior({combo_key('AsAh'): .2}, 'call')

    def test_impossible_joint_ranges_are_not_sampled_forever(self):
        r = ComboRange((('AsAh', 1),), 'source')
        with self.assertRaisesRegex(StrategyError, 'NO_COMPATIBLE'):
            DealSampler((r, r), RIVER)

    def test_joint_sampling_preserves_the_collision_conditioned_product(self):
        r = (ComboRange((('AsKs', 1), ('AhKh', 1)), 'hero'),
             ComboRange((('AsQd', 1), ('AdQs', 1)), 'villain'))
        sampler, rng = DealSampler(r, ('2c', '3d', '4h')), random.Random(13)
        n = 6000
        first = sum(combo_key(sampler.sample(rng)[0][0]) == combo_key('AsKs') for _ in range(n))
        # AsKs permits one villain combo; AhKh permits two, so its marginal is 1/3.
        self.assertAlmostEqual(first / n, 1 / 3, delta=.025)

    def test_range_distribution_fingerprint_changes_on_priors(self):
        a = ComboRange((('AsAh', 1),), 'source')
        b = ComboRange((('AsAh', .5),), 'source')
        self.assertNotEqual(a.fingerprint, b.fingerprint)

    def test_malformed_classes_and_extra_players_are_rejected(self):
        for hand in ('AKsh', 'AAo', '', 'AXs', 'AK'):
            with self.subTest(hand=hand), self.assertRaises(StrategyError):
                ComboRange.from_classes({hand: 1}, 'source')
        r = ComboRange((('AsAh', 1),), 'source')
        with self.assertRaisesRegex(StrategyError, 'TWO_RANGES'):
            DealSampler((r, r, r), RIVER)


class BettingEconomicsTests(unittest.TestCase):
    def test_ip_check_ends_street_but_oop_check_does_not(self):
        self.assertEqual(apply_action(ip_state(), Action('check')).terminal, 'showdown')
        oop = BettingState(RIVER, 25, (50, 50), oop=0)
        after = apply_action(oop, Action('check'))
        self.assertFalse(after.terminal)
        self.assertEqual(after.actor, 1)

    def test_flop_turn_river_pot_and_stack_arithmetic(self):
        root = ip_state(('As', '7d', '2c'), 5.5, (22.5, 22.5))
        bet = apply_action(root, Action('bet', 5.5 / 3))
        self.assertAlmostEqual(bet.pot_bb, 7.333333333)
        self.assertAlmostEqual(bet.call_cost_bb, 1.833333333)
        turn = reveal(apply_action(bet, Action('call', bet.call_cost_bb)), 'Ts')
        self.assertAlmostEqual(turn.pot_bb, 9.166666666)
        turn = apply_action(turn, Action('check'))
        turn_bet = apply_action(turn, Action('bet', turn.pot_bb * 2 / 3))
        river = reveal(apply_action(turn_bet, Action('call', turn_bet.call_cost_bb)), '4h')
        self.assertAlmostEqual(river.pot_bb, 21.388888888, places=6)
        self.assertAlmostEqual(river.stacks[0], 14.555555556, places=6)

    def test_raise_amount_is_additional_not_raise_to(self):
        root = BettingState(RIVER, 10, (30, 30), oop=0)
        bet = apply_action(root, Action('bet', 4))
        raised = apply_action(bet, Action('raise', 12))
        self.assertEqual(raised.committed, (4, 12))
        self.assertEqual(raised.call_required_bb, 8)
        self.assertEqual(raised.last_full_raise_bb, 8)

    def test_pot_raise_menu_uses_pot_after_call(self):
        bet = apply_action(BettingState(RIVER, 10, (50, 50)), Action('bet', 4))
        actions = legal_actions(bet, BetMenu((.5,), 2, False))
        # Current pot14 + call4 -> half18=9; contribution call4 + raise9 =13.
        self.assertIn(Action('raise', 13), actions)

    def test_check_raise_is_in_a_menu_with_two_aggressions(self):
        s = BettingState(RIVER, 10, (50, 50), oop=0)
        s = apply_action(s, Action('check'))
        s = apply_action(s, Action('bet', 5))
        actions = legal_actions(s, BetMenu((1,), 2, False))
        self.assertTrue(any(a.kind == 'raise' for a in actions))

    def test_short_all_in_does_not_reopen_raise(self):
        s = apply_action(BettingState(RIVER, 10, (20, 7)), Action('bet', 4))
        s = apply_action(s, Action('all_in', 7))
        self.assertFalse(s.raise_rights[0])
        self.assertFalse(is_legal(s, Action('raise', 10)))
        self.assertTrue(is_legal(s, Action('call', 3)))

    def test_full_raise_reopens_action(self):
        s = apply_action(BettingState(RIVER, 10, (20, 20)), Action('bet', 4))
        s = apply_action(s, Action('raise', 8))
        self.assertTrue(s.raise_rights[0])
        self.assertTrue(is_legal(s, Action('raise', 8)))

    def test_unmatched_overbet_is_refunded_when_short_stack_calls(self):
        s = BettingState(RIVER, 40, (10, 70), committed=(0, 30), oop=0,
                         last_full_raise_bb=30, acted=(False, True))
        terminal = apply_action(s, Action('call', 10))
        self.assertEqual(terminal.pot_bb, 30)
        self.assertEqual(terminal.stacks, (0, 90))
        self.assertEqual(terminal.pot_bb + sum(terminal.stacks), s.pot_bb + sum(s.stacks))
        win = terminal_utility(terminal, (('Kh', 'Kd'), ('Ah', 'Qd')), s) + s.pot_bb / 2
        self.assertEqual(win, 20)  # eligible existing pot20, not current visible40

    def test_all_in_runs_to_river_without_more_bets(self):
        s = ip_state(('As', '7d', '2c'), 10, (5, 5))
        s = apply_action(s, Action('all_in', 5))
        s = apply_action(s, Action('call', 5))
        s = reveal(s, 'Ts')
        self.assertEqual(s.needs_cards, 1)
        s = reveal(s, '4h')
        self.assertEqual(s.terminal, 'showdown')
        self.assertEqual(s.pot_bb, 20)

    def test_normal_bet_does_not_turn_into_all_in_when_size_is_absent(self):
        actions = legal_actions(ip_state(pot=25, stacks=(5, 5)), BetMenu((2 / 3,), 1, True))
        self.assertEqual([a.kind for a in actions], ['check', 'all_in'])
        self.assertTrue(is_legal(ip_state(pot=25, stacks=(5, 5)), Action('bet', 2)))

    def test_no_arbitrary_deep_stack_cutoff(self):
        for stack in (30, 80, 200, 5000):
            with self.subTest(stack=stack):
                actions = legal_actions(ip_state(pot=10, stacks=(stack, stack)), BetMenu())
                self.assertTrue(any(a.kind == 'bet' for a in actions))

    def test_check_illegal_when_facing_price(self):
        s = apply_action(ip_state(), Action('bet', 10))
        self.assertFalse(is_legal(s, Action('check')))


class FixedPolicyEconomicTests(unittest.TestCase):
    def test_turn_call_cannot_use_the_unrevealed_river_to_avoid_losing_calls(self):
        root = BettingState(('Kc', '8s', '3d', 'Ts'), 10, (1, 0), committed=(0, 1),
                            oop=1, acted=(False, True))
        ranges = (ComboRange((('As5s', 1),), 'hero'), ComboRange((('AhKd', 1),), 'villain'))
        gap = exact_hu_gap(root, ranges, BetMenu((1,), 0, False), lambda s, h: [.5, .5])
        # Nine winning spades among 44 legal rivers. Call EV = 9/44*11 - 1 = 1.25.
        # A clairvoyant player folding the other rivers would incorrectly get 90/44.
        self.assertAlmostEqual(gap['best_response_centered_bb'][0] + 5, 1.25)
        self.assertEqual(gap['joint_deals_including_ordered_runouts'], 44)

    def test_exact_turn_evaluation_integrates_all_runouts_before_action_selection(self):
        root = BettingState(('Kc', '8s', '3d', 'Ts'), 10, (1, 0), committed=(0, 1),
                            oop=1, acted=(False, True))
        ranges = (ComboRange((('As5s', 1),), 'hero'), ComboRange((('AhKd', 1),), 'villain'))
        result = evaluate_profile(root, ranges, BetMenu((1,), 0, False), lambda s, h: [0, 1],
                                  exact_runouts=True)
        self.assertEqual(result['deals'], 44)
        self.assertAlmostEqual(result['root_ev_player0_bb'], 1.25)
        self.assertIsNone(result['mc_stderr_bb'])

    def test_best_response_cannot_fold_only_against_hidden_value_hands(self):
        root = BettingState(RIVER, 30, (50, 30), committed=(0, 20), oop=1,
                            acted=(False, True), last_full_raise_bb=20)
        ranges = (ComboRange((('As5s', 1),), 'hero'),
                  ComboRange((('AhKd', 1), ('QsJs', 1)), 'villain'))
        gap = exact_river_gap(root, ranges, BetMenu((1,), 0, False), lambda s, h: [.5, .5])
        # Correct BR: always call, EV .5*30-.5*20=5. An oracle would make 15.
        self.assertAlmostEqual(gap['best_response_centered_bb'][0] + 15, 5)

    def test_positive_river_bluff_loses_to_check_with_showdown_value(self):
        hero = ComboRange((('As5s', 1), ('6c5c', 1)), 'synthetic-hero')
        calls = ('AhKd', 'AdKh', 'AcKs', 'KhQd')
        folds = ('QsJs', 'QhJh', 'QdJd', 'Js9s', 'Jh9h', '9s7s')
        villain = ComboRange(tuple((c, 1) for c in calls + folds), 'fixed-response-model')
        menu, root = BetMenu((2 / 3,), 0, False), ip_state()

        def policy(state, own_hand):
            actions = legal_actions(state, menu)
            if state.actor == 0:
                return [1 / len(actions)] * len(actions)
            want = 'call' if combo_key(own_hand) in {combo_key(c) for c in calls} else 'fold'
            return [float(a.kind == want) for a in actions]

        result = evaluate_profile(root, (hero, villain), menu, policy, exact_river=True)
        self.assertEqual(result['deals'], 20)
        a = result['rows'][(root.key(), combo_key('As5s'))]['action_ev_bb']
        b = result['rows'][(root.key(), combo_key('6c5c'))]['action_ev_bb']
        self.assertAlmostEqual(a[0], 15)
        self.assertAlmostEqual(a[1], 25 / 3, places=7)
        self.assertAlmostEqual(b[0], 0)
        self.assertAlmostEqual(b[1], 25 / 3, places=7)

    def test_royal_board_call_keeps_tie_value(self):
        root = BettingState(('As', 'Ks', 'Qs', 'Js', 'Ts'), 15, (20, 15),
                            committed=(0, 5), oop=0, acted=(False, True), last_full_raise_bb=5)
        ranges = (ComboRange((('2c3d', 1),), 'h'), ComboRange((('4c5d', 1),), 'v'))
        menu = BetMenu((1,), 0, False)
        result = evaluate_profile(root, ranges, menu, lambda s, h: [.5, .5], exact_river=True)
        values = result['rows'][(root.key(), combo_key('2c3d'))]['action_ev_bb']
        self.assertEqual(values, [0, 5])

    def test_oop_check_value_includes_ip_bet_instead_of_free_showdown(self):
        root = BettingState(RIVER, 25, (50, 50), oop=0)
        ranges = (ComboRange((('6c5c', 1),), 'hero'), ComboRange((('QsJs', 1),), 'villain'))
        menu = BetMenu((2 / 3,), 0, False)

        def policy(s, hand):
            actions = legal_actions(s, menu)
            desired = 'call' if s.call_required_bb else 'bet' if s.actor == 1 else 'check'
            return [float(a.kind == desired) for a in actions]

        result = evaluate_profile(root, ranges, menu, policy, exact_river=True)
        values = result['rows'][(root.key(), combo_key('6c5c'))]['action_ev_bb']
        self.assertAlmostEqual(values[0], -25 * 2 / 3, places=7)


class NativeAdapterContracts(unittest.TestCase):
    def test_native_parser_cutoff_does_not_drop_rare_combos(self):
        r = ComboRange((('AsAh', 1), ('KsKh', .001)), 'prior')
        text, factor, symmetric = native_range(r)
        weights = dict((k, float(w)) for k, w in (v.split(':') for v in text.split(',')))
        self.assertGreater(min(weights.values()), .005)
        self.assertAlmostEqual(weights[combo_key('KsKh')] / weights[combo_key('AsAh')], .001)
        self.assertEqual(factor, 10)
        self.assertFalse(symmetric)

    def test_only_complete_suit_symmetric_classes_allow_isomorphism(self):
        r = ComboRange.from_classes({'AA': .5, 'AKs': .2, 'AKo': .1}, 'prior')
        text, _, symmetric = native_range(r)
        self.assertTrue(symmetric)
        self.assertIn('AKs:0.2', text)
        self.assertNotIn('AsKs', text)
        changed = dict(r.weights)
        changed[combo_key('AsKs')] = .3
        _, _, symmetric = native_range(ComboRange(tuple(changed.items()), 'changed'))
        self.assertFalse(symmetric)

    def test_board_conditioning_is_not_mistaken_for_a_symmetric_prior(self):
        r = ComboRange.from_classes({'A5s': 1}, 'prior')
        self.assertFalse(native_range(r.without(('As',)))[2])

    def test_native_money_scale_and_last_measured_iteration_are_explicit(self):
        root = BettingState(('As', '7d', '2c'), 5.5, (22.5, 22.5), actor=1, oop=1)
        text, settings = input_commands(context(), root, river_ranges(), BetMenu(), iterations=100)
        self.assertIn('set_pot 5500\n', text)
        self.assertIn('set_effective_stack 22500\n', text)
        self.assertIn('set_max_iteration 101\n', text)
        self.assertIn('set_bet_sizes ip,river,raise,100\n', text)
        self.assertEqual(settings['native_raise_limit'], 4)

    def test_native_rounded_size_is_preserved_instead_of_replaced_by_nominal_fraction(self):
        action = native_action('BET 1833.000000', ip_state(pot=5.5), 1000)
        self.assertEqual(action.amount_bb, 1.833)
        self.assertNotEqual(action.amount_bb, 5.5 / 3)

    def test_native_illegal_raise_is_rejected_instead_of_filtered_and_renormalized(self):
        bet = apply_action(BettingState(RIVER, 10, (50, 50)), Action('bet', 4))
        with self.assertRaisesRegex(StrategyError, 'ILLEGAL_IN_DECLARED'):
            native_action('RAISE 5000', bet, 1000)  # call4 + raise1 < previous bet4

    def test_native_cannot_solve_an_ip_state_as_an_oop_root(self):
        with self.assertRaisesRegex(StrategyError, 'OOP_FIRST'):
            input_commands(context(), ip_state(), river_ranges(), BetMenu())


class SolverAndPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trainer = trained_river(8000)
        cls.evaluation = evaluate_profile(cls.trainer.root, cls.trainer.ranges, cls.trainer.menu,
                                         cls.trainer.probabilities, exact_river=True)
        cls.bundle = attach_evaluation(cls.trainer.export(), cls.evaluation)
        cls.policy = CompiledPolicy(cls.bundle)

    def decision(self, **kwargs):
        return replace(DecisionState(context(), ip_state(), ('As', '5s'), 'table1', 'hand1'), **kwargs)

    def test_training_reduces_independent_imperfect_information_best_response_gap(self):
        early = trained_river(100)
        first = exact_river_gap(early.root, early.ranges, early.menu, early.probabilities)
        last = exact_river_gap(self.trainer.root, self.trainer.ranges, self.trainer.menu,
                               self.trainer.probabilities)
        self.assertLess(last['nash_conv_bb'], first['nash_conv_bb'])
        self.assertLess(last['nash_conv_bb'], 1.0)

    def test_flop_traversal_reaches_turn_and_river_without_future_features(self):
        root = ip_state(('As', '7d', '2c'), 5.5, (22.5, 22.5))
        ranges = (ComboRange((('QsJs', 1), ('AhQh', 1)), 'hero'),
                  ComboRange((('7c6c', 1), ('KhKd', 1)), 'villain'))
        t = CFRTrainer(context(), root, ranges, BetMenu((1 / 3,), 0, False), seed=9).train(20)
        self.assertEqual({s.street for s, _ in t.nodes.values()}, {'FLOP', 'TURN', 'RIVER'})
        for state, _ in t.nodes.values():
            self.assertNotIn('runout', state.to_dict())
            self.assertNotIn('villain_cards', state.to_dict())
        CompiledPolicy(t.export())

    def test_training_budget_does_not_claim_convergence_or_an_incomplete_iteration(self):
        t = CFRTrainer(context(), ip_state(), river_ranges(), max_nodes=1).train(100)
        self.assertTrue(t.budget_exhausted)
        self.assertEqual(t.iterations, 0)
        self.assertFalse(t.export()['quality']['converged'])
        self.assertIsNone(t.export()['quality']['global_gap_bb'])

    def test_final_policy_evs_are_evaluated_separately_from_training(self):
        before = self.trainer.export()
        row = before['nodes'][ip_state().key()]['combos'][combo_key('As5s')]
        self.assertIsNone(row['action_ev_bb'])
        row = self.bundle['nodes'][ip_state().key()]['combos'][combo_key('As5s')]
        self.assertTrue(all(isinstance(v, float) for v in row['action_ev_bb'].values()))

    def test_same_hand_on_new_frames_preserves_mix_selection(self):
        d = self.decision()
        first = choose(self.policy, d)
        for i in range(20):
            self.assertEqual(choose(self.policy, replace(d, revision=i))['action_id'], first['action_id'])

    def test_position_context_change_cannot_reuse_policy(self):
        d = self.decision(context=GameContext(('UTG', 'BB'), arrival_id='different-prior'))
        with self.assertRaisesRegex(StrategyError, 'CONTEXT_MISMATCH'):
            choose(self.policy, d)

    def test_stack_change_is_a_miss_not_nearest_neighbor(self):
        with self.assertRaisesRegex(StrategyError, 'PUBLIC_NODE_MISS'):
            choose(self.policy, self.decision(betting=replace(ip_state(), stacks=(200, 200))))

    def test_off_policy_combo_is_not_an_automatic_fold(self):
        with self.assertRaisesRegex(StrategyError, 'OFF_POLICY'):
            choose(self.policy, self.decision(hero_cards=('7c', '6c')))

    def test_compiled_output_has_two_size_ids_when_both_are_legal(self):
        t = CFRTrainer(context(), ip_state(), river_ranges(), BetMenu((1 / 3, 2 / 3), 0, False)).train(10)
        p = CompiledPolicy(t.export())
        candidates = choose(p, self.decision())['candidates']
        self.assertEqual(len({c['action_id'] for c in candidates}), 3)
        self.assertEqual(len([c for c in candidates if c['action'] == 'bet']), 2)

    def test_policy_cannot_smuggle_a_different_size_or_probability(self):
        for mutate in ('size', 'probability', 'nan'):
            b = copy.deepcopy(self.bundle)
            n = b['nodes'][ip_state().key()]
            if mutate == 'size':
                n['actions'][1]['amount_bb'] = 999
            else:
                r = n['combos'][combo_key('As5s')]['frequencies']
                r[next(iter(r))] = 1.5 if mutate == 'probability' else math.nan
            with self.subTest(mutate=mutate), self.assertRaises(StrategyError):
                CompiledPolicy(b)

    def test_compressed_atomic_roundtrip_preserves_policy_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'policy.json.gz'
            save_policy(self.bundle, p)
            loaded = CompiledPolicy.load(p)
            self.assertEqual(loaded.fingerprint, self.policy.fingerprint)
            self.assertFalse(p.with_name(p.name + '.tmp').exists())

    def test_observed_bet_updates_hero_range_and_call_updates_villain_range(self):
        line = LinePolicy(self.policy)
        original = [r.fingerprint for r in line.ranges]
        line.observe(Action('bet', 25 * 2 / 3))
        self.assertNotEqual(line.ranges[0].fingerprint, original[0])
        self.assertEqual(line.ranges[1].fingerprint, original[1])
        hero_after = line.ranges[0].fingerprint
        line.observe(Action('call', line.state.call_cost_bb))
        self.assertEqual(line.ranges[0].fingerprint, hero_after)
        self.assertNotEqual(line.ranges[1].fingerprint, original[1])
        self.assertEqual(line.state.terminal, 'showdown')

    def test_action_outside_tree_does_not_corrupt_range_or_state(self):
        line = LinePolicy(self.policy)
        before = (line.state, line.ranges)
        with self.assertRaisesRegex(StrategyError, 'OUTSIDE_COMPILED'):
            line.observe(Action('bet', 7))
        self.assertEqual((line.state, line.ranges), before)

    def test_observer_missing_timeline_is_visible_and_does_not_fabricate_context(self):
        result = PolicyObserver(self.policy).advise(table_key='t', hand_key='h', table_state={},
                hero_cards=('As', '5s'), board=RIVER, mode='chip_ev', stage='mid')
        self.assertEqual(result['status'], 'CONTEXT_MISSING')
        self.assertFalse(result['execution_allowed'])

    def test_observer_rechecks_hand_money_source_and_cards(self):
        d = self.decision()
        payload = asdict(d)
        payload['range_sha256'] = [r.fingerprint for r in self.policy.ranges]
        state = dict(strategy_state=payload, positions={'hero': 'BTN', 'v1': 'BB'},
                     pot={'pot_bb': 25}, to_call={'to_call_bb': 0},
                     active_seats=['hero', 'v1'],
                     seats={'hero': {'stack_bb': 50}, 'v1': {'stack_bb': 50}})
        kw = dict(table_key='table1', hand_key='hand1', table_state=state,
                  hero_cards=('As', '5s'), board=RIVER, mode='chip_ev', stage='mid')
        observer = PolicyObserver(self.policy)
        self.assertEqual(observer.advise(**kw)['status'], 'ADVICE')
        self.assertFalse(observer.advise(**kw)['execution_allowed'])
        self.assertIn('IDENTITY_MISMATCH', observer.advise(**dict(kw, hand_key='hand2'))['reason'])
        state['pot']['pot_bb'] = 26
        self.assertIn('MONEY_MISMATCH', observer.advise(**kw)['reason'])

    def test_flop_card_order_is_equivalent_but_turn_suit_is_not(self):
        d = self.decision()
        permuted = replace(d, betting=replace(d.betting, board=('3d', 'Kc', '8s', 'Ts', '2h')))
        a, b = choose(self.policy, d), choose(self.policy, permuted)
        self.assertEqual(a['node_id'], b['node_id'])
        self.assertEqual(a['selection_id'], b['selection_id'])
        different_turn = replace(d, betting=replace(d.betting, board=('Kc', '8s', '3d', 'Th', '2h')))
        with self.assertRaisesRegex(StrategyError, 'PUBLIC_NODE_MISS'):
            choose(self.policy, different_turn)

    def test_independent_counterexample_detects_native_chance_bug_even_when_sum_gap_is_zero(self):
        folder = Path(__file__).parent / 'docs/software-hu-engine-20261115'
        before = CompiledPolicy.load(folder / 'chance-before.json.gz')
        after = CompiledPolicy.load(folder / 'chance-after.json.gz')
        self.assertEqual(before.quality['global_gap_bb'], 0)
        self.assertFalse(before.quality['native_metric_independently_verified'])
        self.assertGreater(before.data['gap']['max_per_player_br_difference_bb'], .21)
        self.assertTrue(after.quality['native_metric_independently_verified'])
        self.assertLess(after.data['gap']['max_per_player_br_difference_bb'], 1e-4)
        self.assertEqual(after.data['evaluation']['root_ev_player0_bb'], 10)

    def test_full_turn_river_subgame_matches_native_per_player_values_after_chance_fix(self):
        folder = Path(__file__).parent / 'docs/software-hu-engine-20261115'
        p = CompiledPolicy.load(folder / 'policy-turn-conditional-fixed.json.gz')
        result = exact_hu_gap(p.root, p.ranges, p.menu, p.probabilities, actions_fn=p.actions)
        self.assertAlmostEqual(result['nash_conv_bb'], p.quality['global_gap_bb'], delta=1e-5)
        for a, b in zip(result['best_response_centered_bb'], p.quality['native_last_best_response_centered_bb']):
            self.assertAlmostEqual(a, b, delta=1e-5)
        self.assertEqual(result['joint_deals_including_ordered_runouts'], 176)
        self.assertTrue(p.quality['native_metric_independently_verified'])

    def test_local_exact_response_avoids_negative_bluff_without_claiming_a_new_equilibrium(self):
        folder = Path(__file__).parent / 'docs/software-hu-engine-20261115'
        p = CompiledPolicy.load(folder / 'policy-turn-conditional-fixed.json.gz')
        d = DecisionState.from_dict(json.loads((folder / 'query-river-QsJs.json').read_text()))
        advice = choose(p, d, selection_mode='exact_response')
        self.assertEqual(advice['recommended'], 'check')
        self.assertIsNone(advice['quality']['selected_profile_global_gap_bb'])
        self.assertIn('LOCAL_RESPONSE_TO_FROZEN_MODEL_NOT_A_NEW_EQUILIBRIUM_PROFILE', advice['caveats'])

    def test_local_response_does_not_maximize_unknown_or_monte_carlo_ev(self):
        p = CompiledPolicy(self.trainer.export())
        with self.assertRaisesRegex(StrategyError, 'REQUIRES_EXACT'):
            choose(p, self.decision(), selection_mode='exact_response')


if __name__ == '__main__':
    unittest.main()
