"""TRAVA do executor de clique da Suprema (offline): resolve o alvo do plano, respeita o
DRY-RUN (nao clica) e, armado, clica a coord certa — tudo SEM janela real (client_rect_screen
monkeypatchado) e SEM clicar de verdade (mover injetado)."""
import unittest

import suprema_click as C
import suprema_act as A


class ResolveTarget(unittest.TestCase):
    def test_raise_vai_pro_botao_aumentar(self):
        act, frac = C.resolve_target({'action': A.RAISE, 'chips': 1500, 'preset': '3X'})
        self.assertEqual(act, A.RAISE)
        self.assertEqual(frac, C.BUTTON_LAYOUT[A.RAISE])

    def test_fold_check_call(self):
        self.assertEqual(C.resolve_target({'action': A.FOLD})[1], C.BUTTON_LAYOUT[A.FOLD])
        self.assertEqual(C.resolve_target({'action': A.CHECK})[1], C.BUTTON_LAYOUT[A.CHECK])
        self.assertEqual(C.resolve_target({'action': A.CALL})[1], C.BUTTON_LAYOUT[A.CALL])

    def test_wait_e_abstain_sem_alvo(self):
        self.assertEqual(C.resolve_target({'action': A.WAIT}), (A.WAIT, None))
        self.assertEqual(C.resolve_target({'action': A.ABSTAIN}), (A.ABSTAIN, None))


class BuildSequence(unittest.TestCase):
    def test_fold_um_clique(self):
        self.assertEqual(C.build_sequence({'action': A.FOLD}), [C.BUTTON_LAYOUT[A.FOLD]])

    def test_raise_com_preset_3_cliques(self):
        seq = C.build_sequence({'action': A.RAISE, 'preset': '3X'})
        self.assertEqual(seq, [C.BUTTON_LAYOUT[A.RAISE], C.PRESET_LAYOUT['3X'], C.PRESET_LAYOUT['confirm']])

    def test_raise_sem_preset_so_abre_e_confirma(self):
        seq = C.build_sequence({'action': A.RAISE})
        self.assertEqual(seq, [C.BUTTON_LAYOUT[A.RAISE], C.PRESET_LAYOUT['confirm']])

    def test_all_in_abre_allin_confirma(self):
        seq = C.build_sequence({'action': A.ALL_IN})
        self.assertEqual(seq, [C.BUTTON_LAYOUT[A.RAISE], C.PRESET_LAYOUT['all_in'], C.PRESET_LAYOUT['confirm']])

    def test_wait_vazio(self):
        self.assertEqual(C.build_sequence({'action': A.WAIT}), [])


class Execute(unittest.TestCase):
    def setUp(self):
        self._orig = C.client_rect_screen
        C.client_rect_screen = lambda hwnd: (100, 50, 500, 900)   # janela fake

    def tearDown(self):
        C.client_rect_screen = self._orig

    @staticmethod
    def _expected(frac):
        return (int(100 + frac[0] * 500), int(50 + frac[1] * 900))

    def test_dry_run_nao_clica(self):
        out = C.execute({'action': A.FOLD}, hwnd=1, armed=False)
        self.assertFalse(out['clicked'])
        self.assertEqual(out['reason'], 'DRY_RUN')
        self.assertEqual(out['screen'], [self._expected(C.BUTTON_LAYOUT[A.FOLD])])

    def test_armado_raise_sequencia(self):
        cliques = []
        out = C.execute({'action': A.RAISE, 'preset': '2X'}, hwnd=1, armed=True,
                        mover=lambda x, y: cliques.append((x, y)), sleeper=lambda s: None)
        self.assertTrue(out['clicked'])
        self.assertEqual(cliques, [self._expected(C.BUTTON_LAYOUT[A.RAISE]),
                                   self._expected(C.PRESET_LAYOUT['2X']),
                                   self._expected(C.PRESET_LAYOUT['confirm'])])

    def test_sem_alvo_nao_clica(self):
        cliques = []
        out = C.execute({'action': A.WAIT}, hwnd=1, armed=True, mover=lambda x, y: cliques.append((x, y)))
        self.assertFalse(out['clicked'])
        self.assertIn('SEM_ALVO', out['reason'])
        self.assertEqual(cliques, [])


if __name__ == '__main__':
    unittest.main()
