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


class Execute(unittest.TestCase):
    def setUp(self):
        # janela fake: client em (100,50), 500x900 -> frac vira coord de tela
        self._orig = C.client_rect_screen
        C.client_rect_screen = lambda hwnd: (100, 50, 500, 900)

    def tearDown(self):
        C.client_rect_screen = self._orig

    @staticmethod
    def _expected(frac):
        # client (100,50,500,900): x=100+fx*500, y=50+fy*900 (int)
        return (int(100 + frac[0] * 500), int(50 + frac[1] * 900))

    def test_dry_run_nao_clica(self):
        out = C.execute({'action': A.FOLD}, hwnd=1, armed=False)
        self.assertFalse(out['clicked'])
        self.assertEqual(out['reason'], 'DRY_RUN')
        self.assertEqual(out['screen'], self._expected(C.BUTTON_LAYOUT[A.FOLD]))

    def test_armado_clica_a_coord(self):
        cliques = []
        out = C.execute({'action': A.RAISE}, hwnd=1, armed=True, mover=lambda x, y: cliques.append((x, y)))
        self.assertTrue(out['clicked'])
        self.assertEqual(len(cliques), 1)
        self.assertEqual(cliques[0], self._expected(C.BUTTON_LAYOUT[A.RAISE]))

    def test_sem_alvo_nao_clica(self):
        cliques = []
        out = C.execute({'action': A.WAIT}, hwnd=1, armed=True, mover=lambda x, y: cliques.append((x, y)))
        self.assertFalse(out['clicked'])
        self.assertIn('SEM_ALVO', out['reason'])
        self.assertEqual(cliques, [])


if __name__ == '__main__':
    unittest.main()
