"""TRAVA DE REGRESSAO do SIZE de open (Eduardo: o size e DELE; proibido inventar
4x). open = 2.0x SEMPRE, exceto 2.5x no INICIO (late reg aberta) E deep (>40bb).
Se alguem mudar isso, a SUITE FALHA. Ver nvt-autoridade-eduardo-decide /
nvt-squeeze-3bet-shove-curto."""
import unittest

import sizing


class TestOpenSizeRegressao(unittest.TestCase):
    def test_default_e_2x_sempre(self):
        # sem sinal de inscricao -> 2.0x em qualquer stack (NUNCA 4x, nunca 3x)
        for stk in (10, 20, 25, 40, 50, 80, 100):
            self.assertEqual(sizing.open_size_bb(stk), 2.0,
                             f'open {stk}bb (reg fechada) tem que ser 2.0x')

    def test_25x_so_deep_e_inicio(self):
        # 2.5x SO com inscricao aberta (inicio) E deep (>40bb)
        self.assertEqual(sizing.open_size_bb(100, registration_open=True), 2.5)
        self.assertEqual(sizing.open_size_bb(60, registration_open=True), 2.5)
        # short, mesmo no inicio -> 2.0x (nao e deep)
        self.assertEqual(sizing.open_size_bb(25, registration_open=True), 2.0)
        self.assertEqual(sizing.open_size_bb(40, registration_open=True), 2.0)  # ==40 nao e >40

    def test_nunca_inventa_outro_size(self):
        # o open SO pode ser 2.0 ou 2.5 — jamais 3x/4x
        for stk in (5, 15, 25, 40, 55, 100):
            for reg in (False, True):
                self.assertIn(sizing.open_size_bb(stk, registration_open=reg), (2.0, 2.5))

    def test_constantes_travadas(self):
        self.assertEqual(sizing.OPEN_RAISE_BB, 2.0)
        self.assertEqual(sizing.OPEN_RAISE_DEEP_BB, 2.5)
        self.assertEqual(sizing.OPEN_DEEP_THRESHOLD_BB, 40)


if __name__ == '__main__':
    unittest.main()
