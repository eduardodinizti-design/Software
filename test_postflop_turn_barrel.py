"""Trava a heurística do barril de turn (3 gavetas polarizadas) + tipos de carta de turn,
e a PROMOÇÃO (a carta de turn dirige a decisão: barril não-valor checa em turn do caller)."""
import unittest

import postflop_turn_barrel as tb
from postflop_advisor import advise_postflop


def _st(pot, tocall, stack=40):
    return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=tocall),
                hero=dict(stack_bb=stack), n_opponents=1)


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


class PromocaoDecisao(unittest.TestCase):
    def test_nao_valor_checa_em_turn_que_completa_flush(self):
        # flop two-tone de copas + turn de copas (3ª); hero KJ sem copas = ar -> CHECK
        a = advise_postflop(_st(6, 0), ['Kd', 'Js'], ['Qh', '7h', '2c', 'Ah'],
                            street='TURN', aggressor='hero')
        self.assertEqual(a['recommended'], 'check')
        self.assertIn('TURN_BARREL_CHECK_CALLER_CARD', a['caveats'])

    def test_valor_segue_apostando_em_turn_que_completa_flush(self):
        # mesmo turn, hero com set de 7 = valor -> NÃO é dampeado (aposta)
        a = advise_postflop(_st(6, 0), ['7c', '7s'], ['Qh', '7h', '2c', 'Ah'],
                            street='TURN', aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertNotIn('TURN_BARREL_CHECK_CALLER_CARD', a.get('caveats', []))

    def test_nao_valor_checa_em_turn_que_completa_sequencia(self):
        # flop J-T-8 (alto, não é low-connected) + turn 9 -> completa sequência; hero K2 = ar
        a = advise_postflop(_st(6, 0), ['Kd', '2s'], ['Jh', 'Td', '8c', '9s'],
                            street='TURN', aggressor='hero')
        self.assertEqual(a['recommended'], 'check')
        self.assertIn('TURN_BARREL_CHECK_CALLER_CARD', a['caveats'])

    def test_turn_blank_nao_dampeia(self):
        # turn blank: a promoção não intervém (segue a lógica normal do advisor)
        a = advise_postflop(_st(6, 0), ['Kd', 'Js'], ['Qh', '7d', '2c', '3s'],
                            street='TURN', aggressor='hero')
        self.assertNotIn('TURN_BARREL_CHECK_CALLER_CARD', a.get('caveats', []))


class AgressorOvercard(unittest.TestCase):
    def test_barrela_polo_fraco_com_equidade_em_overcard(self):
        # flop 9-6-2 + turn K (overcard); hero QJ = ar com gutshot (precisa do T) -> barrela
        a = advise_postflop(_st(6, 0), ['Qd', 'Jc'], ['9h', '6d', '2c', 'Ks'],
                            street='TURN', aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertIn('TURN_BARREL_OVERCARD_AGGRESSOR', a['caveats'])

    def test_nao_barrela_ar_seco_sem_equidade(self):
        # mesmo turn overcard, hero 7-3 sem par/draw/overcards -> check (não spewa ar seco)
        a = advise_postflop(_st(6, 0), ['7d', '3s'], ['9h', '6d', '2c', 'Ks'],
                            street='TURN', aggressor='hero')
        self.assertEqual(a['recommended'], 'check')
        self.assertNotIn('TURN_BARREL_OVERCARD_AGGRESSOR', a.get('caveats', []))

    def test_turn_blank_nao_dispara_barril_overcard(self):
        # turn blank (3): não é overcard -> o barril do lado agressor não intervém
        a = advise_postflop(_st(6, 0), ['Qd', 'Jc'], ['9h', '6d', '2c', '3s'],
                            street='TURN', aggressor='hero')
        self.assertNotIn('TURN_BARREL_OVERCARD_AGGRESSOR', a.get('caveats', []))


if __name__ == '__main__':
    unittest.main()
