"""Testes do conselho pós-flop (heurística fundamentada, exploratória)."""
import unittest

from postflop_advisor import advise_postflop


def state(pot, to_call, stack=40.0):
    return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=to_call),
                seats=dict(hero=dict(stack_bb=stack, occupied=True)),
                positions=dict(hero='BTN'))


class AbstentionTests(unittest.TestCase):
    def test_no_board(self):
        r = advise_postflop(state(10, 0), ['As', 'Kd'], [])
        self.assertEqual(r['status'], 'ABSTAIN')
        self.assertEqual(r['reason'], 'NO_BOARD')

    def test_pot_unknown(self):
        r = advise_postflop(state(None, 0), ['As', 'Kd'], ['Ah', '9h', '3d'])
        self.assertEqual(r['reason'], 'POT_UNKNOWN')

    def test_to_call_unknown(self):
        r = advise_postflop(dict(pot=dict(pot_bb=10), to_call=dict(to_call_bb=None),
                                 seats=dict(hero=dict(stack_bb=40))),
                            ['As', 'Kd'], ['Ah', '9h', '3d'])
        self.assertEqual(r['reason'], 'TO_CALL_UNKNOWN')

    def test_card_conflict(self):
        r = advise_postflop(state(10, 0), ['As', 'Kd'], ['As', '9h', '3d'])
        self.assertEqual(r['reason'], 'HERO_BOARD_CARD_CONFLICT')


class FacingBetTests(unittest.TestCase):
    def test_strong_dry_board_raises(self):
        r = advise_postflop(state(10, 4), ['3c', '3h'], ['As', '9h', '3d'])  # set
        self.assertEqual(r['recommended'], 'raise')
        self.assertIn('size_bb', r['sizing'])
        self.assertFalse(r['execution_allowed'])

    def test_strong_but_board_makes_flush_calls_only(self):
        r = advise_postflop(state(10, 4), ['Ks', 'Kc'], ['9s', '7s', '2s'])  # overpair, monotone
        self.assertEqual(r['recommended'], 'call')
        self.assertIn('BOARD_MAY_BEAT_ONE_PAIR_CALL_ONLY', r['caveats'])

    def test_flush_draw_good_odds_calls(self):
        r = advise_postflop(state(6, 1), ['As', 'Ks'], ['Qs', '7s', '2d'])
        self.assertEqual(r['recommended'], 'call')
        self.assertIn('DRAW_EQUITY_RULE_OF_2_AND_4', r['caveats'])
        self.assertGreater(r['draw_equity'], r['pot_odds'])

    def test_flush_draw_bad_odds_folds(self):
        r = advise_postflop(state(2, 6), ['As', 'Ks'], ['Qs', '7s', '2d'])
        self.assertEqual(r['recommended'], 'fold')
        self.assertLess(r['draw_equity'], r['pot_odds'])

    def test_top_pair_small_bet_calls(self):
        r = advise_postflop(state(10, 3), ['As', 'Qc'], ['Ah', '9h', '3d'])
        self.assertEqual(r['recommended'], 'call')
        self.assertIn('BLUFFCATCH_DEFEND_TO_MDF', r['caveats'])

    def test_top_pair_big_bet_abstains(self):
        r = advise_postflop(state(10, 20), ['As', 'Qc'], ['Ah', '9h', '3d'])
        self.assertEqual(r['status'], 'ABSTAIN')
        self.assertEqual(r['reason'], 'BLUFFCATCH_VS_BIG_BET_NEEDS_READS')

    def test_marginal_pair_folds(self):
        r = advise_postflop(state(10, 5), ['9s', 'Qc'], ['Ah', '9h', '3d'])  # second pair
        self.assertEqual(r['recommended'], 'fold')
        self.assertIn('MARGINAL_BLUFFCATCH_FOLD_DEFAULT_EXPLOITABLE', r['caveats'])

    def test_air_folds(self):
        r = advise_postflop(state(10, 5), ['7s', '4d'], ['Ah', 'Kc', '9s'])
        self.assertEqual(r['recommended'], 'fold')

    def test_mdf_and_pot_odds_reported(self):
        r = advise_postflop(state(10, 5), ['9s', 'Qc'], ['Ah', '9h', '3d'])
        self.assertAlmostEqual(r['pot_odds'], 5 / 15, places=3)
        self.assertAlmostEqual(r['mdf'], 10 / 15, places=3)


class CheckedToTests(unittest.TestCase):
    def test_strong_value_bets(self):
        r = advise_postflop(state(8, 0), ['3c', '3h'], ['As', '9h', '3d'])
        self.assertEqual(r['recommended'], 'bet')
        self.assertGreater(r['sizing']['size_bb'], 0)

    def test_strong_draw_semibluffs(self):
        r = advise_postflop(state(8, 0), ['As', 'Ks'], ['Qs', '7s', '2d'])
        self.assertEqual(r['recommended'], 'bet')
        self.assertIn('SEMI_BLUFF_NEGA_EQUITY_E_CRESCE_POTE', r['caveats'])

    def test_top_pair_dry_bets_thin(self):
        r = advise_postflop(state(8, 0), ['As', 'Qc'], ['Ah', '9c', '3d'])
        self.assertEqual(r['recommended'], 'bet')
        self.assertLess(r['sizing']['fraction'], 0.5)

    def test_air_checks(self):
        r = advise_postflop(state(8, 0), ['7s', '4d'], ['Ah', 'Kc', '9s'])
        self.assertEqual(r['recommended'], 'check')

    def test_marginal_checks(self):
        r = advise_postflop(state(8, 0), ['9s', 'Qc'], ['Ah', '9h', '3d'])
        self.assertEqual(r['recommended'], 'check')


class Phase2EquityTests(unittest.TestCase):
    """Com range do vilão, o CALL passa a ser por equity exata (Monte Carlo, seed fixa)."""

    def test_top_pair_calls_vs_wide_value(self):
        # AQ top pair de ases vs overpairs/AK: hero à frente da maioria -> call.
        r = advise_postflop(state(10, 3), ['As', 'Qc'], ['Ah', '9h', '3d'],
                            villain_range=['KK', 'QQ', 'JJ', 'AK'], iters=2000)
        self.assertEqual(r['recommended'], 'call')
        self.assertIn('BLUFFCATCH_EQUITY_DRIVEN', r['caveats'])
        self.assertGreater(r['equity'], r['pot_odds'])

    def test_top_pair_folds_vs_sets(self):
        # Mesmo top pair vs um range só de sets: atrás -> fold.
        r = advise_postflop(state(10, 3), ['As', 'Qc'], ['Ah', '9h', '3d'],
                            villain_range=['AA', '99', '33'], iters=2000)
        self.assertEqual(r['recommended'], 'fold')
        self.assertLess(r['equity'], r['pot_odds'] + 0.05)

    def test_big_bet_still_abstains_with_range(self):
        r = advise_postflop(state(10, 20), ['As', 'Qc'], ['Ah', '9h', '3d'],
                            villain_range=['KK', 'QQ', 'AK'], iters=2000)
        self.assertEqual(r['status'], 'ABSTAIN')
        self.assertEqual(r['reason'], 'BLUFFCATCH_VS_BIG_BET_NEEDS_READS')
        self.assertIsNotNone(r['equity'])      # equity reportada, mas abstém

    def test_draw_equity_exact_overrides_rule(self):
        r = advise_postflop(state(6, 1), ['As', 'Ks'], ['Qs', '7s', '2d'],
                            villain_range=['QQ', '77', '22'], iters=2000)
        self.assertEqual(r['recommended'], 'call')
        self.assertIn('EQUITY_VS_VILLAIN_PREFLOP_RANGE', r['caveats'])
        self.assertNotIn('draw_equity', r)     # usa equity exata, não a regra 2-e-4

    def test_marginal_calls_vs_air_range(self):
        r = advise_postflop(state(10, 5), ['9s', 'Qc'], ['Ah', '9h', '3d'],
                            villain_range=['KQ', 'KJ', 'QJ', 'JT'], iters=2000)
        self.assertEqual(r['recommended'], 'call')
        self.assertIn('MARGINAL_EQUITY_DRIVEN', r['caveats'])

    def test_marginal_folds_vs_value_range(self):
        r = advise_postflop(state(10, 5), ['9s', 'Qc'], ['Ah', '9h', '3d'],
                            villain_range=['AA', 'AK', 'AQ', '99'], iters=2000)
        self.assertEqual(r['recommended'], 'fold')

    def test_equity_is_deterministic(self):
        a = advise_postflop(state(10, 3), ['As', 'Qc'], ['Ah', '9h', '3d'],
                            villain_range=['KK', 'QQ', 'AK'], iters=2000)
        b = advise_postflop(state(10, 3), ['As', 'Qc'], ['Ah', '9h', '3d'],
                            villain_range=['KK', 'QQ', 'AK'], iters=2000)
        self.assertEqual(a['equity'], b['equity'])

    def test_range_accepts_hand_strings_and_combos(self):
        from preflop_equity import hand_to_combos
        combos = [(c, 1.0) for c in hand_to_combos('KK')] + [(c, 1.0) for c in hand_to_combos('QQ')]
        a = advise_postflop(state(10, 3), ['As', 'Qc'], ['Ah', '9h', '3d'],
                            villain_range=['KK', 'QQ'], iters=2000)
        b = advise_postflop(state(10, 3), ['As', 'Qc'], ['Ah', '9h', '3d'],
                            villain_range=combos, iters=2000)
        self.assertEqual(a['equity'], b['equity'])

    def test_no_range_keeps_phase1_behavior(self):
        r = advise_postflop(state(10, 3), ['As', 'Qc'], ['Ah', '9h', '3d'])
        self.assertIsNone(r['equity'])
        self.assertEqual(r['recommended'], 'call')     # bluffcatch Fase 1
        self.assertIn('BLUFFCATCH_DEFEND_TO_MDF', r['caveats'])


class PotTypeGatingTests(unittest.TestCase):
    """3bet pot e multiway pós-flop: abstenção explícita rotulada, não o heurístico."""

    def test_three_bet_pot_abstains_labeled(self):
        r = advise_postflop(state(10, 4), ['3c', '3h'], ['As', '9h', '3d'], pot_type='three_bet')
        self.assertEqual(r['status'], 'ABSTAIN')
        self.assertEqual(r['reason'], 'POSTFLOP_THREE_BET_POT_NOT_COVERED')
        self.assertIsNone(r['recommended'])
        self.assertEqual(r['made'], 'set')          # mantém a leitura
        self.assertIn('POSTFLOP_POT_TYPE_UNCOVERED', r['caveats'])
        self.assertFalse(r['execution_allowed'])

    def test_multiway_abstains_labeled(self):
        r = advise_postflop(state(10, 4), ['3c', '3h'], ['As', '9h', '3d'], pot_type='multiway')
        self.assertEqual(r['reason'], 'POSTFLOP_MULTIWAY_NOT_COVERED')
        self.assertIsNotNone(r['pot_odds'])         # leitura preservada

    def test_single_raised_still_advises(self):
        r = advise_postflop(state(10, 4), ['3c', '3h'], ['As', '9h', '3d'], pot_type='single_raised')
        self.assertEqual(r['status'], 'ADVICE')
        self.assertEqual(r['recommended'], 'raise')

    def test_unknown_pot_type_falls_to_phase1(self):
        r = advise_postflop(state(10, 4), ['3c', '3h'], ['As', '9h', '3d'], pot_type='unknown')
        self.assertEqual(r['status'], 'ADVICE')     # não bloqueia: Fase 1

    def test_default_none_unchanged(self):
        r = advise_postflop(state(10, 4), ['3c', '3h'], ['As', '9h', '3d'])
        self.assertEqual(r['status'], 'ADVICE')


class ContractTests(unittest.TestCase):
    def test_never_allows_execution(self):
        for st, hero, board in [
            (state(10, 4), ['3c', '3h'], ['As', '9h', '3d']),
            (state(6, 1), ['As', 'Ks'], ['Qs', '7s', '2d']),
            (state(8, 0), ['7s', '4d'], ['Ah', 'Kc', '9s']),
            (state(10, 20), ['As', 'Qc'], ['Ah', '9h', '3d']),
        ]:
            r = advise_postflop(st, hero, board)
            self.assertFalse(r['execution_allowed'])
            self.assertTrue(r['exploratory'])
            self.assertIn('POSTFLOP_HEURISTIC_NO_SOLVER', r['caveats'])

    def test_phase_marker_on_advice_and_abstain(self):
        # O marcador phase='postflop' é o que impede o operador armado de executar
        # pós-flop (o executor só olha status/elegibilidade), então deve estar sempre.
        adv = advise_postflop(state(10, 4), ['3c', '3h'], ['As', '9h', '3d'])
        self.assertEqual(adv['phase'], 'postflop')
        ab = advise_postflop(state(None, 0), ['As', 'Kd'], ['Ah', '9h', '3d'])
        self.assertEqual(ab['status'], 'ABSTAIN')
        self.assertEqual(ab['phase'], 'postflop')

    def test_spr_computed(self):
        r = advise_postflop(state(10, 0, stack=40), ['3c', '3h'], ['As', '9h', '3d'])
        self.assertAlmostEqual(r['spr'], 4.0, places=2)

    def test_icm_mode_flagged(self):
        r = advise_postflop(state(10, 0), ['3c', '3h'], ['As', '9h', '3d'], mode='icm')
        self.assertIn('ICM_PKO_NOT_APPLIED_POSTFLOP', r['caveats'])

    def test_street_inferred(self):
        self.assertEqual(advise_postflop(state(8, 0), ['As', 'Qc'], ['Ah', '9c', '3d'])['street'], 'FLOP')
        self.assertEqual(advise_postflop(state(8, 0), ['As', 'Qc'], ['Ah', '9c', '3d', '5s'])['street'], 'TURN')
        self.assertEqual(advise_postflop(state(8, 0), ['As', 'Qc'], ['Ah', '9c', '3d', '5s', 'Jd'])['street'], 'RIVER')


if __name__ == '__main__':
    unittest.main()
