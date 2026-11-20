"""Trava o capítulo de RIVER IP (polarização + valor relativo): piso de valor sobe quando o
river completa draws; disciplina de valor (promoção) faz a mão que perdeu valor dar check."""
import unittest

from postflop_eval import classify_board
from postflop_advisor import advise_postflop
import postflop_river as rv


def _st(pot, tocall, stack=40):
    return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=tocall),
                hero=dict(stack_bb=stack), n_opponents=1)


class ValorRelativo(unittest.TestCase):
    def test_board_blank_top_pair_e_valor(self):
        bc = classify_board(['Ah', '7d', '2c', 'Ks', '3h'])   # seco, sem flush/seq
        self.assertFalse(rv.is_draw_complete(bc))
        self.assertTrue(rv.river_value_ok('top_pair', bc))
        self.assertTrue(rv.river_value_ok('two_pair', bc))

    def test_board_flush_derruba_two_pair(self):
        bc = classify_board(['Ah', '7h', '2c', 'Kh', '3h'])   # 4 copas -> flush possível
        self.assertTrue(rv.is_draw_complete(bc))
        self.assertFalse(rv.river_value_ok('two_pair', bc))
        self.assertFalse(rv.river_value_ok('top_pair', bc))
        self.assertTrue(rv.river_value_ok('flush', bc))
        self.assertTrue(rv.river_value_ok('set', bc))

    def test_board_sequencia_derruba_overpair(self):
        bc = classify_board(['9h', '8d', '7c', '6s', '2h'])   # sequência no board
        self.assertTrue(rv.is_draw_complete(bc))
        self.assertFalse(rv.river_value_ok('overpair', bc))
        self.assertTrue(rv.river_value_ok('straight', bc))

    def test_tier_e_size_hint(self):
        bc_dry = classify_board(['Ah', '7d', '2c', 'Ks', '3h'])
        self.assertEqual(rv.river_tier('top_pair', {}, bc_dry), 'value')
        self.assertEqual(rv.river_tier('air', {}, bc_dry), 'bluff')
        self.assertEqual(rv.river_tier('second_pair', {}, bc_dry), 'check')
        self.assertEqual(rv.river_size_hint('full_house', bc_dry), 'overbet')
        self.assertEqual(rv.river_size_hint('top_pair', bc_dry), 'big')
        self.assertEqual(rv.river_size_hint('second_pair', bc_dry), 'none')


class PromocaoRiver(unittest.TestCase):
    def test_two_pair_checa_em_river_de_flush(self):
        # board 4 copas no river; hero A7 (two pair A+7, sem copas) perdeu valor -> check
        a = advise_postflop(_st(10, 0), ['Ad', '7s'], ['Ah', '7h', '2c', 'Kh', '3h'],
                            street='RIVER', aggressor='hero')
        self.assertEqual(a['recommended'], 'check')
        self.assertIn('RIVER_CHECK_PERDEU_VALOR_RELATIVO', a['caveats'])

    def test_flush_segue_apostando_em_river_de_flush(self):
        # hero com flush (A+K de copas? usa 2 copas) -> valor, não é dampeado
        a = advise_postflop(_st(10, 0), ['Qh', 'Jh'], ['Ah', '7h', '2c', 'Kh', '3h'],
                            street='RIVER', aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertNotIn('RIVER_CHECK_PERDEU_VALOR_RELATIVO', a.get('caveats', []))

    def test_top_pair_value_beta_em_river_blank(self):
        # river blank seco (A-K-9-8-4, sem flush/sequência): top pair segue sendo valor (aposta)
        a = advise_postflop(_st(10, 0), ['Ad', 'Qs'], ['Ah', '9d', '8c', 'Ks', '4h'],
                            street='RIVER', aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertNotIn('RIVER_CHECK_PERDEU_VALOR_RELATIVO', a.get('caveats', []))


if __name__ == '__main__':
    unittest.main()
