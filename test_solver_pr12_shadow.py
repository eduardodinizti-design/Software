"""Testes do pacote de sombra As7d2c do PR#12 (flop+turn per-combo, TexasSolver).

Invariantes: decodificação fiel (valores batem com a amostra oficial do release),
isomorfismo de naipe correto, nunca executa, e honesto fora de cobertura."""
import unittest

import solver_pr12_shadow as pr12

BOARD = ['As', '7d', '2c']


class PackTests(unittest.TestCase):
    def test_pacote_carrega(self):
        p = pr12.load_pack()
        self.assertIsNotNone(p)
        self.assertEqual(p['node_counts'], {'FLOP': 10, 'TURN': 2254})
        self.assertFalse(p['ev_available'])
        self.assertEqual(tuple(p['board']), tuple(BOARD))

    def test_cbet_btn_bate_amostra_oficial(self):
        # A amostra 'decisoes-tres-ruas' do release: combo 3sAd, c-bet do BTN ->
        # check 0.00032538, bet 0.99924, all_in 0.00043367.
        r = pr12.flop_cbet(['3s', 'Ad'], BOARD)
        self.assertIsNotNone(r)
        self.assertEqual(r['actor_pos'], 'BTN')
        self.assertEqual(r['street'], 'FLOP')
        self.assertEqual(r['combo'], '3sAd')
        self.assertEqual(r['actions'], ['check', 'bet', 'all_in'])
        self.assertAlmostEqual(r['freq'][0], 0.0003, places=3)
        self.assertAlmostEqual(r['freq'][1], 0.9992, places=3)
        self.assertEqual(r['recommended_shadow'], 'bet')
        self.assertFalse(r['execution_allowed'])
        self.assertIn('POSTFLOP_SOLVER_SHADOW', r['caveats'])

    def test_freq_somam_um_no_cbet(self):
        r = pr12.flop_cbet(['Kd', 'Qh'], BOARD)
        self.assertIsNotNone(r)
        self.assertLess(abs(sum(r['freq']) - 1.0), 1e-3)


class IsoTests(unittest.TestCase):
    def test_isomorfismo_de_naipe_da_mesma_freq(self):
        base = pr12.flop_cbet(['3s', 'Ad'], BOARD)
        # Troca d<->c e s<->h no board e no hero -> As7d2c isomórfico.
        swap = {'s': 'h', 'h': 's', 'd': 'c', 'c': 'd'}
        iso_board = [c[0] + swap[c[1]] for c in BOARD]       # Ah7c2d
        iso_hero = ['3' + swap['s'], 'A' + swap['d']]        # 3hAc
        r = pr12.flop_cbet(iso_hero, iso_board)
        self.assertIsNotNone(r)
        self.assertTrue(r['iso'])
        self.assertEqual(r['freq'], base['freq'])            # simetria: idêntico

    def test_board_nao_isomorfico_retorna_none(self):
        self.assertIsNone(pr12.flop_cbet(['Ah', 'Kd'], ['Ah', 'Kc', '7d']))


class TurnTests(unittest.TestCase):
    def test_no_de_turn_existe_e_per_combo(self):
        # Turn 2d, linha BB-check / BTN-check, BB a agir (chave observada no export).
        hist = ['1:check:0', '0:check:0', 'BOARD:2d']
        r = pr12.lookup(['Kd', 'Qh'], ['As', '7d', '2c', '2d'], hist)
        self.assertIsNotNone(r)
        self.assertEqual(r['street'], 'TURN')
        self.assertEqual(r['board'], ['As', '7d', '2c', '2d'])
        self.assertLess(abs(sum(r['freq']) - 1.0), 1e-3)
        self.assertIn('SOLVER_SHADOW_TURN_LIVE_MATCH_NEEDS_POSTFLOP_HISTORY', r['caveats'])


class HonestyTests(unittest.TestCase):
    def test_combo_fora_do_range_do_ator(self):
        # No c-bet do BTN, o ator é o IP; uma mão fora do range de open -> honesto.
        r = pr12.flop_cbet(['7h', '2h'], BOARD)
        self.assertIsNotNone(r)
        self.assertFalse(r['combo_in_range'])
        self.assertIsNone(r['recommended_shadow'])
        self.assertIn('SOLVER_SHADOW_COMBO_NOT_IN_RANGE', r['caveats'])

    def test_historia_inexistente_retorna_none(self):
        self.assertIsNone(pr12.lookup(['3s', 'Ad'], BOARD, ['9:bogus:0']))

    def test_flop_cbet_so_aceita_3_cartas(self):
        self.assertIsNone(pr12.flop_cbet(['3s', 'Ad'], ['As', '7d', '2c', '2d']))


if __name__ == '__main__':
    unittest.main()
