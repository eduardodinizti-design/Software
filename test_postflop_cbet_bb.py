"""C-bet do PFR IP vs BB (Teoria para c-bet vs BB, Reg-Life): taxonomia dos boards de
PERIGO em que NÃO se c-beta range (checa mais). Classificador + tag no conselho."""
import unittest

from postflop_eval import classify_board
from postflop_advisor import advise_postflop
import postflop_cbet_bb as cb


def st(pot, tocall, stack=40):
    return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=tocall),
                hero=dict(stack_bb=stack), n_opponents=1)


class Classificador(unittest.TestCase):
    def test_low_connected(self):
        self.assertEqual(cb.cbet_check_category(classify_board(['6c', '4d', '2h'])), 'low_connected')
        self.assertEqual(cb.cbet_check_category(classify_board(['9c', '8d', '5h'])), 'low_connected')

    def test_mid_paired(self):
        self.assertEqual(cb.cbet_check_category(classify_board(['7c', '7d', '4h'])), 'mid_paired')
        self.assertEqual(cb.cbet_check_category(classify_board(['5c', '5d', '2h'])), 'mid_paired')

    def test_ace_high_monotone(self):
        self.assertEqual(cb.cbet_check_category(classify_board(['Ah', '9h', '5h'])), 'ace_high_monotone')

    def test_monotone(self):
        self.assertEqual(cb.cbet_check_category(classify_board(['Kh', '9h', '5h'])), 'monotone')

    def test_boards_de_cbet_range_sao_none(self):
        self.assertIsNone(cb.cbet_check_category(classify_board(['Ah', '9c', '3d'])))   # A-alto seco
        self.assertIsNone(cb.cbet_check_category(classify_board(['Qc', '5d', '4h'])))   # Q-alto seco
        self.assertIsNone(cb.cbet_check_category(classify_board(['9c', '6d', '2h'])))   # baixo DESconectado
        self.assertIsNone(cb.cbet_check_category(classify_board(['Kc', 'Kd', '9h'])))   # pareado ALTO
        self.assertTrue(cb.is_cbet_range_board(classify_board(['Ah', '9c', '3d'])))


class TagNoConselho(unittest.TestCase):
    def test_board_perigo_tagueia_quando_hero_agressor(self):
        a = advise_postflop(st(6, 0), ['Kc', 'Qd'], ['Kh', '9h', '5h'], aggressor='hero')
        self.assertIn('CBET_VS_BB_PERIGO_MONOTONE', a['caveats'])

    def test_board_seguro_nao_tagueia(self):
        a = advise_postflop(st(6, 0), ['Ah', 'Qc'], ['Ah', '9c', '3d'], aggressor='hero')
        self.assertFalse(any(c.startswith('CBET_VS_BB_PERIGO_') for c in a['caveats']))

    def test_agressor_desconhecido_nao_tagueia(self):
        a = advise_postflop(st(6, 0), ['Kc', 'Qd'], ['Kh', '9h', '5h'])
        self.assertFalse(any(c.startswith('CBET_VS_BB_PERIGO_') for c in a['caveats']))


if __name__ == '__main__':
    unittest.main()
