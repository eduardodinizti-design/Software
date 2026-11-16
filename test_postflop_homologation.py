"""Testes da homologação pós-flop e da camada 'solver-preferido nos spots cobertos'.

Garante: (1) o harness mede e expõe o leak da heurística; (2) onde o solver é DECISIVO
e per-combo, a recomendação final vira a do solver — sem liberar execução, sem tocar nó
MISTO nem o lado agregado `def`."""
import unittest

import os

import postflop_homologation as homolog
import solver_cbet_shadow as scs
import table_advisor as ta
from postflop_advisor import advise_postflop

BOARD = ['8h', '2s', '2d']


def _advise(hero, board=BOARD, to_call=0, hero_pos='BTN', villain_pos='BB'):
    seats = {'hero': {'occupied': True, 'stack_bb': 23},
             'bb': {'occupied': True, 'stack_bb': 23}}
    state = {'positions': {'hero': hero_pos, 'bb': villain_pos}, 'seats': seats,
             'pot': {'pot_bb': 5.5}, 'to_call': {'to_call_bb': to_call}}
    adv = advise_postflop(state, hero, board, street='FLOP', mode='chip_ev',
                          aggressor=('hero' if hero_pos == 'BTN' else villain_pos),
                          pot_type='single_raised')
    ta._attach_solver_shadow(adv, {'aggressor': 'hero'}, seats, state,
                             hero, {'cards': board, 'street': 'FLOP'}, 'single_raised', 'chip_ev')
    return adv


class HarnessTests(unittest.TestCase):
    def test_harness_mede_e_expoe_o_leak(self):
        rep = homolog.run()
        self.assertGreater(rep['total'], 40000)
        # A heurística NÃO é solver-acurada neste spot: concordância baixa (documentado).
        self.assertLess(rep['decisive_agreement_pct'], 70.0)
        # O leak dominante é PASSIVO (heurística passa onde o solver aposta).
        passivo = sum(rep['leak_passivo_heur_check_solver_bet'].values())
        agressivo = sum(rep['leak_agressivo_heur_bet_solver_check'].values())
        self.assertGreater(passivo, agressivo)
        self.assertIn('air', rep['leak_passivo_heur_check_solver_bet'])


class TurnHomologationTests(unittest.TestCase):
    def test_turn_harness_roda_e_tem_estrutura(self):
        # Subconjunto p/ rapidez; valida o mecanismo (não a estatística completa).
        rep = homolog.run_turn(max_nodes=120)
        self.assertGreater(rep['total'], 1000)
        self.assertEqual(rep['board'], 'As7d2c')
        self.assertIsNotNone(rep['decisive_agreement_pct'])
        self.assertIn('BB', rep['by_actor'])
        self.assertTrue(0.0 <= rep['agreement_pct'] <= 100.0)
        # os dois leaks são tabulados (direções opostas existem no turn)
        self.assertTrue(rep['leak_passivo_heur_check_solver_bet']
                        or rep['leak_agressivo_heur_bet_solver_check'])


class TurnRawHomologTests(unittest.TestCase):
    """run_turn_raw sobre um dump BRUTO sintético mínimo (sem depender de solves reais)."""
    def _mini_dump(self):
        # flop As7d2c: BB(1) bet -> BTN(0) call -> chance 2d -> turn BB(1) check/bet.
        turn = {'node_type': 'action_node', 'player': 1,
                'actions': ['CHECK', 'BET 3.000000'],
                'strategy': {'strategy': {'Kd Qh'.replace(' ', ''): [0.1, 0.9],
                                          'Js Th'.replace(' ', ''): [0.9, 0.1]}},
                'childrens': {}}
        chance = {'node_type': 'chance_node', 'dealcards': {'2d': turn}}
        call = {'node_type': 'action_node', 'player': 0, 'actions': ['CALL', 'FOLD'],
                'childrens': {'CALL': chance}}
        root = {'node_type': 'action_node', 'player': 1,
                'actions': ['CHECK', 'BET 2.000000'], 'childrens': {'BET 2.000000': call}}
        return root

    def test_parse_e_homologa_turn_bruto(self):
        import json as _j
        import tempfile
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'As7d2c.json')
        with open(p, 'w', encoding='utf-8') as fh:
            _j.dump(self._mini_dump(), fh)
        r = homolog.run_turn_raw(p, max_combos_per_node=10, max_nodes_per_board=10)
        self.assertEqual(r['boards'], 1)
        self.assertGreaterEqual(r['total'], 2)       # 2 combos no nó de turn
        self.assertIn('As7d2c', r['by_board'])
        self.assertIsNotNone(r['agreement_pct'])


class SolverPreferredTests(unittest.TestCase):
    def test_override_decisivo_bet_sobre_heuristica_passiva(self):
        # AK em 822: heurística dá check; solver aposta decisivo -> final = bet do solver.
        adv = _advise(['Ah', 'Kd'])
        self.assertEqual(adv['heuristic_recommended'], 'check')
        self.assertEqual(adv['recommended'], 'bet')
        self.assertEqual(adv['recommended_source'], 'solver_shadow')
        self.assertFalse(adv['execution_allowed'])      # gate intacto
        self.assertIn('SOLVER_PREFERRED_ON_COVERED_SPOT', adv['caveats'])
        self.assertEqual(adv['sizing']['solver_size'], 'b33')
        self.assertAlmostEqual(adv['sizing']['size_bb'], 1.8, places=1)

    def test_no_misto_nao_e_sobreposto(self):
        # 33 em 822 é MISTO no solver (~0.57 check / 0.43 bet) -> mantém a heurística.
        adv = _advise(['3d', '3c'])
        sh = adv['solver_shadow']
        self.assertFalse(sh['decisive'])
        self.assertNotIn('recommended_source', adv)      # não sobrepôs
        self.assertNotIn('heuristic_recommended', adv)
        self.assertNotIn('SOLVER_PREFERRED_ON_COVERED_SPOT', adv.get('caveats', []))

    def test_lado_def_nao_sobrepoe_recomendacao(self):
        # Hero BB enfrentando aposta: def é agregado de range -> NÃO vira recomendação.
        adv = _advise(['Qh', 'Jh'], to_call=2.75, hero_pos='BB', villain_pos='BTN')
        # (pot/to_call aqui só exercitam o ramo; o importante é não haver override.)
        self.assertNotEqual(adv.get('recommended_source'), 'solver_shadow')
        if adv.get('solver_shadow'):
            self.assertEqual(adv['solver_shadow']['side'], 'def')

    def test_combo_fora_do_range_nao_sobrepoe(self):
        adv = _advise(['7h', '2h'])     # 72o fora do range de open -> sem freq per-combo
        self.assertFalse(adv['solver_shadow']['combo_in_range'])
        self.assertNotIn('recommended_source', adv)


class ShadowFieldTests(unittest.TestCase):
    def test_lookup_expoe_coarse_e_decisive(self):
        r = scs.lookup(['Ah', 'Kd'], BOARD, hero_pos='BTN', villain_pos='BB',
                       to_call_bb=0, pot_bb=5.5, hero_stack_bb=23, villain_stack_bb=23)
        self.assertIn(r['coarse'], ('check', 'bet'))
        self.assertIsInstance(r['decisive'], bool)
        if r['coarse'] == 'bet':
            self.assertIn(r['bet_size'], ('b33', 'b50', 'b70', 'allin'))


if __name__ == '__main__':
    unittest.main()
