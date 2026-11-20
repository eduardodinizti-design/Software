"""Trava a heurística do barril de turn (3 gavetas polarizadas) + tipos de carta de turn."""
import unittest

import postflop_turn_barrel as tb


class Gavetas(unittest.TestCase):
    def test_valor_aposta_turn_e_river(self):
        for made in ('set', 'two_pair', 'overpair', 'straight', 'flush', 'trips'):
            self.assertEqual(tb.barrel_tier(made, {}), tb.VALUE, made)

    def test_meio_par_mediano_sem_draw_eh_check(self):
        for made in ('second_pair', 'third_pair', 'low_pair', 'underpair', 'top_pair'):
            self.assertEqual(tb.barrel_tier(made, {}), tb.MIDDLE, made)

    def test_par_mediano_com_draw_forte_vira_blefe(self):
        self.assertEqual(tb.barrel_tier('second_pair', {'oesd': True}), tb.BLUFF)

    def test_ar_e_overcards_sao_blefe(self):
        self.assertEqual(tb.barrel_tier('air', {}), tb.BLUFF)
        self.assertEqual(tb.barrel_tier('overcards', {}), tb.BLUFF)
        self.assertEqual(tb.barrel_tier(None, {}), tb.BLUFF)


class TiposDeCarta(unittest.TestCase):
    def test_completa_flush(self):
        # flop two-tone de copas + turn de copas
        self.assertEqual(tb.classify_turn(['Qh', '7h', '2c', 'Ah']), 'completes_flush')

    def test_dobra_topo_meio_baixo(self):
        self.assertEqual(tb.classify_turn(['Qh', '7d', '2c', 'Qs']), 'pairs_top')
        self.assertEqual(tb.classify_turn(['Qh', '7d', '2c', '7s']), 'pairs_mid')
        self.assertEqual(tb.classify_turn(['Qh', '7d', '2c', '2s']), 'pairs_low')

    def test_overcard(self):
        self.assertEqual(tb.classify_turn(['9h', '6d', '2c', 'Ks']), 'overcard')

    def test_completa_sequencia(self):
        # flop 9-8-6 (janela 3) + turn 7 -> 9-8-7-6 (4 em janela de 5) = completa sequência
        self.assertEqual(tb.classify_turn(['9h', '8d', '6c', '7s']), 'completes_straight')

    def test_blank(self):
        # 10-3-2 + 7: não dobra, não flush (rainbow), não overcard, janela < 4
        self.assertEqual(tb.classify_turn(['Th', '3d', '2c', '7s']), 'blank')

    def test_board_de_3_eh_none(self):
        self.assertIsNone(tb.classify_turn(['Qh', '7d', '2c']))


class Lean(unittest.TestCase):
    def test_overcard_barrela_mais(self):
        self.assertEqual(tb.barrel_lean('overcard')['freq_lean'], 'more')

    def test_carta_do_caller_barrela_menos(self):
        for t in ('completes_flush', 'completes_straight', 'pairs_low', 'pairs_mid'):
            self.assertEqual(tb.barrel_lean(t)['freq_lean'], 'less', t)

    def test_flop_nao_range_bet_sobe_frequencia(self):
        self.assertEqual(tb.barrel_lean('blank', range_bet_flop=True)['freq_lean'], 'neutral')
        self.assertEqual(tb.barrel_lean('blank', range_bet_flop=False)['freq_lean'], 'more')

    def test_flop_nao_range_bet_nao_sobe_carta_do_caller(self):
        # carta que favorece o caller continua 'less' mesmo com flop filtrado
        self.assertEqual(tb.barrel_lean('completes_flush', range_bet_flop=False)['freq_lean'], 'less')


if __name__ == '__main__':
    unittest.main()
