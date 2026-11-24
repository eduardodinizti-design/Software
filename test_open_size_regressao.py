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

    def test_iso_sobre_limper_infla_3x_4x_cap_4x(self):
        # Eduardo 23/11 REVERTEU a regra do 21/11: isolar limper INFLA o size (+1bb/limper sobre o
        # open 2x), CAPADO em 4X. 0 limper = open 2x (LEI intacta); 1 limper = 3X; 2 = 4X; 3+ = 4X.
        for limpers, exp in {0: 2.0, 1: 3.0, 2: 4.0, 3: 4.0}.items():
            s = sizing.recommend_size('raise', hero_stack_bb=100, limpers=limpers)
            self.assertEqual(s['size_bb'], exp,
                             f'iso com {limpers} limper(s) tem que ser {exp}bb (Eduardo 23/11)')
        # deep + late reg aberta: open base 2.5x; iso vs 2 limpers = min(2.5+2, 4) = 4.0 (cap)
        s = sizing.recommend_size('raise', hero_stack_bb=100, limpers=2, registration_open=True)
        self.assertEqual(s['size_bb'], 4.0)
        self.assertEqual(sizing.ISO_ADD_PER_LIMPER_BB, 1.0)   # add por limper = 1bb (23/11)
        self.assertEqual(sizing.ISO_MAX_BB, 4.0)              # teto do iso = 4X

    def test_size_from_reading_pote_limpado_sai_3x(self):
        # Eduardo 23/11: UTG+2 abre com 1 limper antes -> iso 3X (reverteu o 2x do 21/11).
        state = dict(
            positions={'hero': 'UTG+2', 'u1': 'UTG', 'bb': 'BB', 'sb': 'SB'},
            bets=[{'seat': 'u1', 'bet_bb': 1.0},   # 1 limper real
                  {'seat': 'bb', 'bet_bb': 1.0}, {'seat': 'sb', 'bet_bb': 0.5},
                  {'seat': 'hero', 'bet_bb': 0.0}],
            seats={'hero': {'stack_bb': 50}}, to_call={'to_call_bb': 1.0})
        s = sizing.size_from_reading('raise', state, 'UTG+2')
        self.assertEqual(sizing.count_limpers(state), 1)   # o limper e real (nao e first-in puro)
        self.assertEqual(s['size_bb'], 3.0)                # 1 limper -> 3X (Eduardo 23/11)


if __name__ == '__main__':
    unittest.main()
