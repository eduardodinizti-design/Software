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

    def test_dry_run_nao_clica(self):
        out = C.execute({'action': A.FOLD}, hwnd=1, armed=False)
        self.assertFalse(out['clicked'])
        self.assertEqual(out['reason'], 'DRY_RUN')
        # FOLD frac (0.18,0.955) -> x=100+0.18*500=190, y=50+0.955*900=909.5->909
        self.assertEqual(out['screen'], (190, 909))

    def test_armado_clica_a_coord(self):
        cliques = []
        out = C.execute({'action': A.RAISE}, hwnd=1, armed=True, mover=lambda x, y: cliques.append((x, y)))
        self.assertTrue(out['clicked'])
        self.assertEqual(len(cliques), 1)
        # RAISE frac (0.80,0.955) -> x=100+400=500, y=50+859.5=909
        self.assertEqual(cliques[0], (500, 909))

    def test_sem_alvo_nao_clica(self):
        cliques = []
        out = C.execute({'action': A.WAIT}, hwnd=1, armed=True, mover=lambda x, y: cliques.append((x, y)))
        self.assertFalse(out['clicked'])
        self.assertIn('SEM_ALVO', out['reason'])
        self.assertEqual(cliques, [])


if __name__ == '__main__':
    unittest.main()
