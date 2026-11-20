"""Frequência bet/check do AGRESSOR (Pós-flop Avançado): em board POLAR (baixo não-pareado)
o agressor NÃO aposta mão média — top pair fino dá CHECK (controle de pote); valor forte +
ar polarizam grande. Gated: só quando o hero É o agressor (iniciativa conhecida)."""
import unittest

from postflop_advisor import advise_postflop
from postflop_eval import classify_board
import postflop_texture as tx


def st(pot, tocall, stack=40):
    return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=tocall),
                hero=dict(stack_bb=stack), n_opponents=1)


class Polarizes(unittest.TestCase):
    def test_board_baixo_polariza(self):
        self.assertTrue(tx.polarizes(classify_board(['9c', '6d', '2h'])))

    def test_board_alto_nao_polariza(self):
        self.assertFalse(tx.polarizes(classify_board(['Ac', '9d', '3h'])))

    def test_board_pareado_nao_polariza(self):
        self.assertFalse(tx.polarizes(classify_board(['7c', '7d', '2h'])))


class FreqAgressor(unittest.TestCase):
    def test_top_pair_board_polar_agressor_cbeta_range(self):
        # LEI Eduardo: PFR continua AGRESSIVO -> top pair em board de c-bet-range c-beta 1/3
        # (não controla pote passivo). Resolve a passividade.
        a = advise_postflop(st(6, 0), ['9h', 'Kc'], ['9c', '6d', '2h'], aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertIn('CBET_PFR_RANGE_1_3', a['caveats'])

    def test_top_pair_board_alto_agressor_aposta(self):
        a = advise_postflop(st(6, 0), ['Ah', 'Qc'], ['Ac', '9d', '3h'], aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')

    def test_top_pair_board_polar_agressor_desconhecido_aposta(self):
        # sem iniciativa conhecida (agressor=None) -> mantém a aposta fina (não vira check)
        a = advise_postflop(st(6, 0), ['9h', 'Kc'], ['9c', '6d', '2h'])
        self.assertEqual(a['recommended'], 'bet')

    def test_valor_forte_vs_bb_c_beta_1_3_range(self):
        # RESOLUÇÃO da tensão de size (aula prática c-bet vs BB): set em 962 no spot PFR IP
        # vs BB c-beta 1/3 RANGE (auto-profit), NÃO polariza grande. Segue sendo bet.
        a = advise_postflop(st(6, 0), ['6c', '6h'], ['9c', '6d', '2h'], aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertAlmostEqual(a['sizing']['fraction'], tx.SMALL, places=2)
        self.assertIn('CBET_VS_BB_SIZE_1_3', a['caveats'])

    def test_low_connected_check_range_vs_bb(self):
        # board baixo CONECTADO (642) vs BB -> CHECK-RANGE: até o set checa (balanceia o turn)
        a = advise_postflop(st(6, 0), ['6c', '6h'], ['6d', '4s', '2h'], aggressor='hero')
        self.assertEqual(a['recommended'], 'check')
        self.assertIn('CBET_VS_BB_CHECK_RANGE_LOW_CONNECTED', a['caveats'])


class EquityBuckets(unittest.TestCase):
    def test_classificador(self):
        self.assertEqual(tx.equity_bucket(0.95), 'nuts')
        self.assertEqual(tx.equity_bucket(0.85), 'strong')
        self.assertEqual(tx.equity_bucket(0.75), 'value')
        self.assertEqual(tx.equity_bucket(0.65), 'medium')
        self.assertEqual(tx.equity_bucket(0.40), 'weak')
        self.assertIsNone(tx.equity_bucket(None))

    def test_caveat_do_bucket_com_range(self):
        a = advise_postflop(st(6, 0), ['9h', 'Kc'], ['9c', '6d', '2h'],
                            aggressor='hero', villain_range=['72o', '83o', '74o', '82o'], seed=1)
        self.assertTrue(any(c.startswith('EQUITY_BUCKET_') for c in a['caveats']))

    def test_bucket_forte_nao_vira_check_no_polar(self):
        # top pair com equidade alta (bucket strong) em board polar -> APOSTA (não check)
        a = advise_postflop(st(6, 0), ['9h', 'Kc'], ['9c', '6d', '2h'],
                            aggressor='hero', villain_range=['72o', '83o', '74o', '82o'], seed=1)
        self.assertEqual(a['recommended'], 'bet')
        self.assertIn('EQUITY_BUCKET_STRONG', a['caveats'])

    def test_bucket_medio_cbeta_range_pfr(self):
        # LEI Eduardo: PFR c-beta RANGE no board de c-bet-range mesmo com equidade mediana
        # (a agressão por vantagem de range supera o controle de pote passivo).
        a = advise_postflop(st(6, 0), ['9h', 'Kc'], ['9c', '6d', '2h'],
                            aggressor='hero', villain_range=['QJo', 'JTo', 'KQo', 'AQo'], seed=1)
        self.assertEqual(a['recommended'], 'bet')


if __name__ == '__main__':
    unittest.main()
