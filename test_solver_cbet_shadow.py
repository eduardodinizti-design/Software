"""Testes da sombra de solver pós-flop (pacote btn_vs_bb_25).

Invariantes do GATE: a sombra NUNCA executa, só fala onde há verdade (spot/flop/nó
cobertos) e por isomorfismo de naipe entrega a MESMA frequência do flop canônico.
Fora da cobertura -> None (não inventa)."""
import json
import os
import random
import unittest

import solver_cbet_shadow as scs

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'strategy_data', 'postflop_solver', 'btn_vs_bb_25.json')
PACK = json.load(open(DATA, encoding='utf-8'))
FLOP0 = scs._parse_flop(PACK['flops'][0]['flop'])          # ex. 8h2s2d

BASE = dict(hero_pos='BTN', villain_pos='BB', to_call_bb=0, pot_bb=5.5,
            hero_stack_bb=23, villain_stack_bb=23)


class PackageTests(unittest.TestCase):
    def test_pacote_existe_e_e_chip_ev(self):
        self.assertEqual(PACK['spot'], 'btn_vs_bb_25')
        self.assertEqual(PACK['grading'], 'freq')
        self.assertEqual(PACK['aggressor'], 'ip')
        self.assertEqual(len(PACK['flops']), 100)

    def test_todas_as_freqs_do_pacote_somam_um(self):
        for entry in PACK['flops']:
            for combo, freq in entry['agg'].items():
                self.assertLess(abs(sum(freq) - 1.0), 1e-2, (entry['flop'], combo))


class AggNodeTests(unittest.TestCase):
    def test_agg_per_combo_no_flop_exato(self):
        r = scs.lookup(['Ah', 'Kd'], FLOP0, **BASE)
        self.assertIsNotNone(r)
        self.assertEqual(r['side'], 'agg')
        self.assertEqual(r['node'], 'btn_cbet_vs_check')
        self.assertTrue(r['per_combo'])
        self.assertTrue(r['combo_in_range'])
        self.assertFalse(r['execution_allowed'])
        self.assertLess(abs(sum(r['freq']) - 1.0), 1e-3)
        self.assertIn(r['recommended_shadow'], scs.AGG_ACTIONS)
        self.assertIn('POSTFLOP_SOLVER_SHADOW', r['caveats'])
        self.assertIn('SOLVER_SHADOW_NOT_FOR_EXECUTION', r['caveats'])
        self.assertIn('SOLVER_SHADOW_FLOP_ONLY', r['caveats'])

    def test_isomorfismo_de_naipe_da_mesma_frequencia(self):
        base = scs.lookup(['Ah', 'Kd'], FLOP0, **BASE)
        swap = {'h': 'c', 'c': 'h', 's': 's', 'd': 'd'}    # h<->c no board e no hero
        iso_board = [c[0] + swap[c[1]] for c in FLOP0]
        iso_hero = ['A' + swap['h'], 'K' + swap['d']]
        r = scs.lookup(iso_hero, iso_board, **BASE)
        self.assertIsNotNone(r)
        self.assertTrue(r['iso'])
        self.assertEqual(r['flop'], PACK['flops'][0]['flop'])
        self.assertEqual(r['freq'], base['freq'])          # simetria de naipe: idêntico
        self.assertEqual(r['recommended_shadow'], base['recommended_shadow'])

    def test_combo_fora_do_range_de_open_e_honesto(self):
        r = scs.lookup(['7h', '2c'], FLOP0, **BASE)        # 72o não entra no open BTN
        self.assertIsNotNone(r)
        self.assertEqual(r['side'], 'agg')
        self.assertFalse(r['combo_in_range'])
        self.assertIsNone(r['recommended_shadow'])
        self.assertIsNone(r['freq'])
        self.assertIn('SOLVER_SHADOW_COMBO_BELOW_RANGE_WEIGHT', r['caveats'])

    def test_btn_enfrentando_aposta_nao_e_coberto(self):
        # x/r (BTN enfrenta check-raise) não está no pacote.
        self.assertIsNone(scs.lookup(['Ah', 'Kd'], FLOP0, hero_pos='BTN', villain_pos='BB',
                                     to_call_bb=5, pot_bb=14, hero_stack_bb=23, villain_stack_bb=23))


class DefNodeTests(unittest.TestCase):
    def test_def_agregado_do_bb_por_size(self):
        # BB enfrenta ~50% do pote: pote antes 5.5, aposta 2.75 -> pot 8.25, to_call 2.75.
        r = scs.lookup(['Qh', 'Jh'], FLOP0, hero_pos='BB', villain_pos='BTN',
                       to_call_bb=2.75, pot_bb=8.25, hero_stack_bb=23, villain_stack_bb=23)
        self.assertIsNotNone(r)
        self.assertEqual(r['side'], 'def')
        self.assertEqual(r['node'], 'bb_vs_cbet')
        self.assertFalse(r['per_combo'])
        self.assertEqual(r['bet_faced'], 'b50')
        self.assertLessEqual(set(r['actions']), {'call', 'raise', 'fold'})
        self.assertIn(r['recommended_shadow'], ('call', 'raise', 'fold'))
        self.assertIn('SOLVER_SHADOW_DEF_RANGE_AGGREGATE_NOT_PER_COMBO', r['caveats'])

    def test_def_all_in_mapeia_para_no_allin(self):
        r = scs.lookup(['Qh', 'Jh'], FLOP0, hero_pos='BB', villain_pos='BTN',
                       to_call_bb=23, pot_bb=28.5, hero_stack_bb=23, villain_stack_bb=23)
        self.assertIsNotNone(r)
        self.assertEqual(r['bet_faced'], 'allin')
        self.assertEqual(set(r['actions']), {'call', 'fold'})

    def test_bb_com_check_nao_e_coberto(self):
        # BB primeiro a agir (to_call 0): donk/check não é o nó agg (IP após check).
        self.assertIsNone(scs.lookup(['Qh', 'Jh'], FLOP0, hero_pos='BB', villain_pos='BTN',
                                     to_call_bb=0, pot_bb=5.5, hero_stack_bb=23, villain_stack_bb=23))


class CoverageGateTests(unittest.TestCase):
    def test_flop_fora_do_pacote_retorna_none(self):
        self.assertIsNone(scs.lookup(['Ah', 'Kd'], ['Ah', 'Kc', '7d'], **BASE))

    def test_profundidade_fora_da_janela_retorna_none(self):
        self.assertIsNone(scs.lookup(['Ah', 'Kd'], FLOP0, hero_pos='BTN', villain_pos='BB',
                                     to_call_bb=0, pot_bb=5.5, hero_stack_bb=50, villain_stack_bb=50))
        self.assertIsNone(scs.lookup(['Ah', 'Kd'], FLOP0, hero_pos='BTN', villain_pos='BB',
                                     to_call_bb=0, pot_bb=5.5, hero_stack_bb=12, villain_stack_bb=12))

    def test_spot_errado_retorna_none(self):
        self.assertIsNone(scs.lookup(['Ah', 'Kd'], FLOP0, hero_pos='CO', villain_pos='BB',
                                     to_call_bb=0, pot_bb=5.5, hero_stack_bb=23, villain_stack_bb=23))

    def test_modo_icm_nao_usa_pacote_chip_ev(self):
        self.assertIsNone(scs.lookup(['Ah', 'Kd'], FLOP0, mode='icm', **BASE))

    def test_turn_e_river_nao_sao_cobertos(self):
        # 4+ cartas: pacote é só flop.
        self.assertIsNone(scs.lookup(['Ah', 'Kd'], FLOP0 + ['9c'], **BASE))

    def test_isomorfismo_casa_boards_variados(self):
        deck = [r + s for r in scs.RANKS for s in scs.SUITS]
        rng = random.Random(0)
        hits = 0
        for _ in range(300):
            board = rng.sample(deck, 3)
            hero = [c for c in ('Ah', 'Kd', 'Qc', 'Js') if c not in board][:2]
            if scs.lookup(hero, board, **BASE) is not None:
                hits += 1
        self.assertGreaterEqual(hits, 1)   # o mecanismo canônico casa, não só o flop exato


if __name__ == '__main__':
    unittest.main()
