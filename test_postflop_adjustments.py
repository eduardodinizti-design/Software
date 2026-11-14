"""Testes dos 3 ajustes pós-flop portados do VisualPilot 2.0 (sizing geométrico,
scare card, pool-underbluff no MDF) e da sua exposição aditiva no advisor."""
import unittest

from postflop_adjustments import (geometric_bet_pct, geometric_street_plan,
                                   pool_adjusted_mdf, remaining_streets,
                                   scare_from_transition, scare_present, SCARE_PENALTY)
from postflop_advisor import advise_postflop


class GeometricSizingTests(unittest.TestCase):
    def test_remaining_streets(self):
        self.assertEqual(remaining_streets('FLOP'), 3)
        self.assertEqual(remaining_streets('turn'), 2)
        self.assertEqual(remaining_streets('RIVER'), 1)
        self.assertIsNone(remaining_streets('x'))

    def test_pct_clamped_and_monotonic(self):
        # Uma rua só: aposta ~o pote já no SPR 1 (s=((1+2)^1-1)/2=1 -> 100%).
        self.assertAlmostEqual(geometric_bet_pct(1.0, 1), 100.0, places=1)
        # Mais ruas p/ o mesmo SPR -> fração por rua MENOR.
        self.assertLess(geometric_bet_pct(4.0, 3), geometric_bet_pct(4.0, 1))
        # Piso e teto.
        self.assertEqual(geometric_bet_pct(0.01, 3), 20.0)
        self.assertEqual(geometric_bet_pct(1000.0, 1), 250.0)

    def test_pct_guards(self):
        self.assertIsNone(geometric_bet_pct(0, 3))
        self.assertIsNone(geometric_bet_pct(2.0, 0))
        self.assertIsNone(geometric_bet_pct(None, 3))

    def test_street_plan_commits_stack_by_river(self):
        plan = geometric_street_plan(spr=4.0, street='FLOP', pot_bb=10.0, stack_bb=40.0)
        self.assertEqual([r['street'] for r in plan], ['FLOP', 'TURN', 'RIVER'])
        # Soma das apostas ~ stack efetivo (compromete tudo até o river), com folga.
        self.assertAlmostEqual(sum(r['bet_bb'] for r in plan), 40.0, delta=4.0)

    def test_street_plan_empty_without_data(self):
        self.assertEqual(geometric_street_plan(2.0, 'FLOP', 0, 40.0), [])
        self.assertEqual(geometric_street_plan(2.0, 'RIVER', 10.0, 0), [])


class ScareCardTests(unittest.TestCase):
    def test_not_present_on_flop(self):
        bc = dict(flush_possible=True, straight_on_board=True, paired=True)
        self.assertFalse(scare_present(bc, 'FLOP')['present'])

    def test_present_kinds_on_turn(self):
        bc = dict(flush_possible=True, straight_on_board=False, paired=True)
        s = scare_present(bc, 'TURN')
        self.assertTrue(s['present'])
        self.assertIn('flush_possible', s['kinds'])
        self.assertIn('board_paired', s['kinds'])

    def test_transition_flush_completes(self):
        # 2 espadas no flop -> 3ª espada no turn fecha o flush.
        self.assertEqual(scare_from_transition(['Ks', '7s', '2d'], ['Ks', '7s', '2d', '9s']),
                         'flush_completes')

    def test_transition_board_pairs(self):
        self.assertEqual(scare_from_transition(['Ks', '7h', '2d'], ['Ks', '7h', '2d', '7c']),
                         'board_pairs')

    def test_transition_overcard_and_brick(self):
        self.assertEqual(scare_from_transition(['9h', '7h', '2d'], ['9h', '7h', '2d', 'Ac']),
                         'overcard')
        self.assertEqual(scare_from_transition(['Kh', '7c', '2d'], ['Kh', '7c', '2d', '3s']),
                         'brick')

    def test_penalty_table_present(self):
        self.assertEqual(set(SCARE_PENALTY), {'flush_completes', 'straight_completes',
                                              'board_pairs', 'overcard'})


class PoolUnderbluffTests(unittest.TestCase):
    def test_discount_only_when_triggered(self):
        self.assertEqual(pool_adjusted_mdf(0.5), 0.5)
        self.assertEqual(pool_adjusted_mdf(0.5, overbet=True), 0.375)
        self.assertEqual(pool_adjusted_mdf(0.5, passive_turned_aggressive=True), 0.375)
        self.assertIsNone(pool_adjusted_mdf(None, overbet=True))


class AdvisorExposureTests(unittest.TestCase):
    """Os ajustes aparecem no conselho SEM mudar a execução (segue exploratório)."""
    def _state(self, pot, to_call, stack=40.0):
        return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=to_call),
                    seats=dict(hero=dict(stack_bb=stack, occupied=True)),
                    positions=dict(hero='BTN'))

    def test_geometric_attached_when_betting_lead(self):
        adv = advise_postflop(self._state(10.0, 0.0, 40.0), ['Ah', 'Kh'], ['Ad', '7s', '2c'],
                              aggressor='hero')
        self.assertIn('geometric', adv)
        self.assertIsInstance(adv['geometric']['pct'], float)
        self.assertFalse(adv['execution_allowed'])

    def test_scare_caveat_on_paired_turn(self):
        adv = advise_postflop(self._state(10.0, 0.0, 40.0), ['Ah', 'Kd'],
                              ['Ad', '7s', '7c', '2h'], aggressor='hero')
        self.assertEqual(adv.get('scare_card'), ['board_paired'])
        self.assertTrue(any(c.startswith('SCARE_CARD_') for c in adv['caveats']))

    def test_pool_underbluff_folds_big_bet_top_pair_without_hud(self):
        # Top pair enfrentando aposta grande (pot odds > 0.40), linha passivo->agressivo:
        # sem HUD o default abstém; com a linha informada, foldamos (pool underbluffa).
        st = self._state(pot=10.0, to_call=9.0, stack=40.0)
        base = advise_postflop(st, ['Ah', 'Qd'], ['Ad', '7s', '2c'], aggressor='hero')
        self.assertEqual(base['status'], 'ABSTAIN')
        pooled = advise_postflop(st, ['Ah', 'Qd'], ['Ad', '7s', '2c'], aggressor='hero',
                                 villain_line='passive_turned_aggressive')
        self.assertEqual(pooled['recommended'], 'fold')
        self.assertFalse(pooled['execution_allowed'])
        self.assertIn('pool_adjusted_mdf', pooled)

    def test_default_behavior_unchanged_without_villain_line(self):
        # Sem villain_line, nada de novo força decisão: top pair vs aposta pequena segue.
        adv = advise_postflop(self._state(10.0, 2.0, 40.0), ['Ah', 'Qd'],
                              ['Ad', '7s', '2c'], aggressor='hero')
        self.assertEqual(adv['status'], 'ADVICE')


if __name__ == '__main__':
    unittest.main()
