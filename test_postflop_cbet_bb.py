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


def st_full(pot, tocall, stack, pos):
    """table_state COMPLETO (seats.hero.stack_bb + positions.hero) p/ exercitar a freq."""
    return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=tocall),
                seats=dict(hero=dict(stack_bb=stack)), positions=dict(hero=pos),
                n_opponents=1)


class FreqPorPosicao(unittest.TestCase):
    def test_early_mais_agressivo(self):
        self.assertEqual(cb.cbet_freq_vs_bb('UTG', 20)['freq'], 0.90)
        self.assertEqual(cb.cbet_freq_vs_bb('UTG', 40)['freq'], 0.85)

    def test_btn_menos_que_early(self):
        self.assertEqual(cb.cbet_freq_vs_bb('BTN', 20)['freq'], 0.70)
        self.assertEqual(cb.cbet_freq_vs_bb('BTN', 40)['freq'], 0.75)
        self.assertEqual(cb.cbet_freq_vs_bb('BTN', 100)['freq'], 0.70)
        # BTN sempre <= early no mesmo stack
        self.assertLess(cb.cbet_freq_vs_bb('BTN', 40)['freq'], cb.cbet_freq_vs_bb('UTG', 40)['freq'])

    def test_mid_entre_os_dois(self):
        self.assertEqual(cb.cbet_freq_vs_bb('CO', 40)['freq'], 0.80)

    def test_posicao_desconhecida_none(self):
        self.assertIsNone(cb.cbet_freq_vs_bb(None, 40))
        self.assertIsNone(cb.cbet_freq_vs_bb('SB', 40))   # SB agressor não coberto


class StackGateDoFlush(unittest.TestCase):
    def test_monotone_perigo_so_deep(self):
        mono = classify_board(['Kh', '9h', '5h'])
        self.assertEqual(cb.cbet_check_category(mono), 'monotone')            # sem stack = perigo
        self.assertEqual(cb.cbet_check_category(mono, stack_bb=100), 'monotone')  # deep = perigo
        self.assertIsNone(cb.cbet_check_category(mono, stack_bb=25))         # short = c-beta

    def test_ace_high_monotone_stack_gate(self):
        ahm = classify_board(['Ah', '9h', '5h'])
        self.assertEqual(cb.cbet_check_category(ahm, stack_bb=80), 'ace_high_monotone')
        self.assertIsNone(cb.cbet_check_category(ahm, stack_bb=30))

    def test_low_connected_nao_e_stack_gated(self):
        lc = classify_board(['6c', '5d', '4h'])
        self.assertEqual(cb.cbet_check_category(lc, stack_bb=25), 'low_connected')   # short ainda perigo
        self.assertEqual(cb.cbet_check_category(lc, stack_bb=100), 'low_connected')


class FreqNoConselho(unittest.TestCase):
    def test_freq_lean_aparece_quando_hero_agressor_ip(self):
        a = advise_postflop(st_full(6, 0, 40, 'UTG'), ['Ks', 'Qd'], ['Ah', '9c', '3d'], aggressor='hero')
        self.assertIn('cbet_vs_bb', a)
        self.assertEqual(a['cbet_vs_bb']['freq_lean']['freq'], 0.85)
        self.assertTrue(any(c == 'CBET_VS_BB_FREQ_85' for c in a['caveats']))

    def test_monotone_short_nao_tagueia_perigo(self):
        # monotone com stack SHORT via table_state completo: não é perigo (c-beta)
        a = advise_postflop(st_full(6, 0, 25, 'BTN'), ['Kc', 'Qd'], ['Kh', '9h', '5h'], aggressor='hero')
        self.assertFalse(any(c.startswith('CBET_VS_BB_PERIGO_') for c in a['caveats']))

    def test_monotone_deep_tagueia_perigo(self):
        a = advise_postflop(st_full(6, 0, 100, 'BTN'), ['Kc', 'Qd'], ['Kh', '9h', '5h'], aggressor='hero')
        self.assertTrue(any(c == 'CBET_VS_BB_PERIGO_MONOTONE' for c in a['caveats']))


if __name__ == '__main__':
    unittest.main()
